# Dual-Mode Approach: Calculating Both Heating and Cooling Simultaneously

## Overview

Instead of using a "sense" parameter to switch between heating and cooling modes, we could implement a more flexible approach that calculates both heating and cooling capabilities simultaneously. This would allow the optimizer to dynamically choose the most efficient mode for each timestep without requiring users to manually configure mode switching.

## Benefits of This Approach

1. **Simplified User Experience**: Users wouldn't need to create separate configurations for different seasons
2. **Smoother Transitions**: Could handle shoulder seasons (spring/fall) more effectively
3. **Optimal Mode Selection**: The optimizer could automatically select the most energy-efficient or cost-effective mode
4. **More Realistic Modeling**: In real-world scenarios, buildings can switch between heating and cooling needs quickly

## Implementation Challenges

1. **Physical System Limitations**: Most heat pumps can't simultaneously heat and cool - they need to switch modes
2. **Increased Computational Complexity**: Would require additional variables and constraints
3. **Anti-Cycling Protection**: Need to prevent rapid switching between heating and cooling
4. **COP Calculations**: Need separate COP calculations for both modes

## Technical Implementation

### 1. Defining Separate Power Variables

Instead of a single `p_deferrable` variable, we would define separate variables for heating and cooling:

```python
p_heat = self.vars["p_heat"][k]  # Heating power
p_cool = self.vars["p_cool"][k]  # Cooling power
```

### 2. Ensuring Mutually Exclusive Operation

We would need to add constraints to ensure the system doesn't heat and cool simultaneously:

```python
# Binary variables to indicate mode (1 = active, 0 = inactive)
heat_active = self.vars["heat_active"][k]  # Binary variable for heating
cool_active = self.vars["cool_active"][k]  # Binary variable for cooling

# Constraints to ensure mutually exclusive operation
constraints.append(heat_active + cool_active <= 1)  # Can't both be active

# Link binary variables to power
constraints.append(p_heat <= heat_active * nominal_power)
constraints.append(p_cool <= cool_active * nominal_power)
```

### 3. Dual COP Calculation

Calculate COPs for both heating and cooling modes:

```python
# Calculate heating COP
heat_cops = utils.calculate_cop_heatpump(
    supply_temperature=heat_supply_temperature,
    carnot_efficiency=heat_efficiency,
    outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
    mode="heat"
)

# Calculate cooling COP
cool_cops = utils.calculate_cop_heatpump(
    supply_temperature=cool_supply_temperature,
    carnot_efficiency=cool_efficiency,
    outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
    mode="cool"
)
```

### 4. Temperature Evolution Model

Update the temperature evolution model to account for both heating and cooling effects:

```python
constraints.append(
    pred_temp[1:] == (
        pred_temp[:-1] 
        + (p_heat[:-1] * heat_cops[:-1] * conversion)  # Heating effect (positive)
        - (p_cool[:-1] * cool_cops[:-1] * conversion)  # Cooling effect (negative)
        - (thermal_losses[:-1] * conversion)
        - (heating_demand[:-1] * conversion)  # Heating demand
        + (cooling_demand[:-1] * conversion)  # Cooling demand
        + (solar_gains[:-1] * conversion)
    )
)
```

### 5. Demand Calculation

Calculate both heating and cooling demand separately:

```python
# Calculate heating demand (when indoor < desired)
heating_demand = calculate_thermal_demand(
    u_value, envelope_area, ventilation_rate, heated_volume,
    indoor_target_temperature, outdoor_temps,
    solar_irradiance, window_area, shgc, internal_gains,
    mode="heat"
)

# Calculate cooling demand (when indoor > desired)
cooling_demand = calculate_thermal_demand(
    u_value, envelope_area, ventilation_rate, heated_volume,
    indoor_target_temperature, outdoor_temps,
    solar_irradiance, window_area, shgc, internal_gains,
    mode="cool"
)
```

## Configuration Approach

Instead of a "sense" parameter, we would use separate supply temperature parameters for heating and cooling:

```json
"thermal_battery": {
  "heat_supply_temperature": 35.0,  // Supply temp for heating mode
  "cool_supply_temperature": 12.0,  // Supply temp for cooling mode
  "heat_carnot_efficiency": 0.4,    // Efficiency for heating
  "cool_carnot_efficiency": 0.45,   // Efficiency for cooling
  "volume": 20.0,
  "start_temperature": 22.0,
  "min_temperatures": [20.0] * 48,  // Lower comfort bound
  "max_temperatures": [26.0] * 48,  // Upper comfort bound
  "u_value": 0.5,
  // ... other parameters ...
}
```

## Potential Challenges

### 1. Switching Frequency

In real systems, frequent switching between heating and cooling can cause wear on equipment. We might need to implement minimum run-time constraints:

```python
# Minimum runtime constraints to prevent short-cycling
min_runtime = 3  # timesteps
constraints.append(enforce_min_runtime(heat_active, min_runtime))
constraints.append(enforce_min_runtime(cool_active, min_runtime))
```

### 2. Computational Complexity

This approach roughly doubles the number of variables and adds several constraints, which could significantly increase solution time. We might need to:

- Study performance impact on various problem sizes
- Consider solver parameter tuning
- Add options to revert to simpler mode-specific solutions for performance-constrained environments

### 3. Sensor Publishing

We would need to publish both heating and cooling information:

```python
# Publish heating and cooling power separately
sensor_name = f"p_heat{k}" 
self._publish_sensor(sensor_name, p_heat_vals, attrs)

sensor_name = f"p_cool{k}"
self._publish_sensor(sensor_name, p_cool_vals, attrs)

# Publish combined power for backward compatibility
sensor_name = f"p_thermal{k}"
self._publish_sensor(sensor_name, p_heat_vals - p_cool_vals, attrs)
```

## Conclusion

Calculating both heating and cooling simultaneously is feasible and offers significant user experience and optimization benefits. However, it increases complexity and computational requirements. 

### Recommendations

1. **Hybrid Approach**: Implement this dual-mode capability but also keep the simpler mode-specific approach as an option.

2. **Configurable Switching Protection**: Allow users to configure minimum runtimes to prevent excessive cycling.

3. **Progressive Implementation**: Implement in phases:
   - First phase: Basic dual-mode capability for simple scenarios
   - Second phase: Add anti-cycling constraints and optimizations
   - Third phase: Refine for performance and edge cases