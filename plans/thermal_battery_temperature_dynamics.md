# Temperature Dynamics for Combined Heating and Cooling Effects

This document details the implementation of the temperature dynamics model for the dual-mode thermal_battery component, accommodating both heating and cooling operations simultaneously.

## 1. Understanding Temperature Dynamics

The temperature dynamics equation describes how the thermal mass temperature evolves over time based on:

1. Heat inputs from the heating system
2. Heat extraction from the cooling system
3. Thermal losses to the environment
4. External heat gains or losses (weather, solar, etc.)
5. Occupancy and internal heat sources

## 2. Current Temperature Evolution Equation

The current thermal_battery implementation uses the following temperature evolution equation:

```
T[t+1] = T[t] + (p_deferrable[t] * COP[t] * conversion) - (losses[t] * conversion) - (heating_demand[t] * conversion) + (solar_gains[t] * conversion)
```

Where:
- `T[t]` is the temperature at timestep t
- `p_deferrable[t]` is the heating power at timestep t
- `COP[t]` is the coefficient of performance at timestep t
- `conversion` is a factor converting kWh to temperature change
- `losses[t]` represents thermal losses to the environment
- `heating_demand[t]` is the building's heating demand
- `solar_gains[t]` represents solar heat gains

## 3. Dual-Mode Temperature Dynamics

For the dual-mode approach, we need to modify this equation to account for both heating and cooling effects:

```
T[t+1] = T[t] + 
         (p_heat[t] * heat_cop[t] * conversion) -     // Heating effect (adds heat)
         (p_cool[t] * cool_cop[t] * conversion) -     // Cooling effect (removes heat)
         (losses[t] * conversion) -                   // Thermal losses to environment
         (heating_demand[t] * conversion) +           // Building heating demand
         (cooling_demand[t] * conversion) +           // Building cooling demand (adds heat)
         (solar_gains[t] * conversion)                // Solar heat gains
```

### 3.1. Implementation in CVXPY

Here's how to implement this equation using CVXPY constraints:

```python
# Temperature evolution constraints
constraints.append(
    pred_temp[1:] == (
        pred_temp[:-1] +
        (p_heat[:-1] * heat_cops[:-1] * conversion) -    # Heating input (positive)
        (p_cool[:-1] * cool_cops[:-1] * conversion) -    # Cooling extraction (negative)
        (thermal_losses[:-1] * conversion) -            # Thermal losses (negative)
        (heating_demand[:-1] * conversion) +            # Heating demand (negative, met by system)
        (cooling_demand[:-1] * conversion) +            # Cooling demand (positive, adds heat to be removed)
        (solar_gains[:-1] * conversion)                 # Solar gains (positive)
    )
)
```

## 4. Sign Convention and Energy Flow

It's crucial to maintain a consistent sign convention throughout the implementation:

### 4.1. Positive Energy Flows (Increase Temperature)

- Heating power (`p_heat`) multiplied by heating COP
- Solar gains
- Internal heat gains
- Cooling demand (represents heat that needs to be removed)

### 4.2. Negative Energy Flows (Decrease Temperature)

- Cooling power (`p_cool`) multiplied by cooling COP
- Thermal losses to environment
- Heating demand (represents heat transfer from the system to the building)

## 5. Thermal Conversion Factor

The conversion factor translates energy (kWh) to temperature change (°C):

```python
# Thermal properties of storage medium
p_concr = 2400         # Density of concrete (kg/m³)
c_concr = 0.88         # Specific heat capacity of concrete (kWh/(kg·K))
volume = hc["volume"]  # Volume of thermal mass (m³)

# Conversion factor from kWh to temperature change
conversion = 3600 / (p_concr * c_concr * volume)
```

This factor depends on:
1. The thermal mass properties (density, specific heat)
2. The volume of the thermal storage
3. Unit conversion factors (3600 seconds per hour)

## 6. Handling Thermal Losses

Thermal losses depend on the temperature difference between the thermal mass and the environment:

```python
# Calculate thermal losses
thermal_losses = utils.calculate_thermal_loss_signed(
    outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
    indoor_temperature=start_temp_float,
    base_loss=loss_coefficient,
)
```

The existing `calculate_thermal_loss_signed` function already handles the sign convention correctly:
- Positive losses: When indoor > outdoor (heat flows out)
- Negative losses: When outdoor > indoor (heat flows in)

This works correctly for both heating and cooling scenarios.

## 7. Initial Temperature Constraint

The temperature prediction must start from the initial temperature:

```python
# Set initial temperature
constraints.append(pred_temp[0] == start_temperature)
```

## 8. Temperature Limits

Both minimum and maximum temperature constraints must be applied:

```python
# Min/max temperature constraints
min_temperatures = self._pad_temp_array(min_temperatures_list, required_len, 18.0)
max_temperatures = self._pad_temp_array(max_temperatures_list, required_len, 26.0)

constraints.append(pred_temp >= min_temperatures)
constraints.append(pred_temp <= max_temperatures)
```

## 9. Implementation Details for Temperature Dynamics

### 9.1. Complete Implementation (Simplified)

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    """
    Handle constraints for thermal battery loads with dual-mode operation.
    """
    # ... (existing setup code)
    
    # Extract power variables (previously created)
    p_heat = self.vars[f"p_heat_{k}"]
    p_cool = self.vars[f"p_cool_{k}"]
    
    # Temperature state variable
    pred_temp = cp.Variable(required_len, name=f"temp_load_{k}")
    constraints.append(pred_temp[0] == start_temp_float)
    
    # Thermal conversion factor
    p_concr = 2400  # kg/m³
    c_concr = 0.88  # kWh/(kg·K)
    conversion = 3600 / (p_concr * c_concr * volume)
    
    # Get or calculate heating and cooling COPs
    heat_cops = params["heat_cops"].value
    cool_cops = params["cool_cops"].value
    
    # Get or calculate heating and cooling demands
    heating_demand = params["heating_demand"].value
    cooling_demand = params["cooling_demand"].value
    solar_gains = params["solar_gains"].value
    
    # Calculate thermal losses
    thermal_losses = params["thermal_losses"].value
    
    # Temperature dynamics constraint
    constraints.append(
        pred_temp[1:] == (
            pred_temp[:-1] + 
            (p_heat[:-1] * heat_cops[:-1] * conversion) -  # Heating effect
            (p_cool[:-1] * cool_cops[:-1] * conversion) -  # Cooling effect
            (thermal_losses[:-1] * conversion) -           # Thermal losses
            (heating_demand[:-1] * conversion) +           # Heating demand (negative)
            (cooling_demand[:-1] * conversion) +           # Cooling demand (positive)
            (solar_gains[:-1] * conversion)                # Solar gains
        )
    )
    
    # Temperature bounds
    constraints.append(pred_temp >= min_temperatures)
    constraints.append(pred_temp <= max_temperatures)
    
    # ... (rest of constraints)
    
    return pred_temp, heating_demand, cooling_demand, solar_gains
```

### 9.2. Handling Thermal Inertia

If thermal inertia is enabled, we need to handle it for both heating and cooling modes:

```python
# Check if thermal inertia is enabled
thermal_inertia = hc.get("thermal_inertia_time_constant", 0.0)

if thermal_inertia > 0:
    # Create heat input filter state variables for both modes
    q_heat_input = cp.Variable(required_len, name=f"q_heat_input_{k}")
    q_cool_input = cp.Variable(required_len, name=f"q_cool_input_{k}")
    
    # Get initial q_input values (from previous solve or initialization)
    q_heat_init = params.get("q_heat_input_start", 
                            cp.Parameter(name=f"q_heat_input_start_{k}", value=0.0))
    q_cool_init = params.get("q_cool_input_start", 
                            cp.Parameter(name=f"q_cool_input_start_{k}", value=0.0))
    
    # Set initial q_input values
    constraints.append(q_heat_input[0] == q_heat_init)
    constraints.append(q_cool_input[0] == q_cool_init)
    
    # Calculate alpha for the low-pass filter
    time_step_hours = self.freq.total_seconds() / 3600
    alpha = min(1.0, time_step_hours / thermal_inertia)
    
    # Apply first-order filter to heating and cooling power
    constraints.append(
        q_heat_input[1:] == q_heat_input[:-1] + 
        alpha * (p_heat[:-1] * heat_cops[:-1] - q_heat_input[:-1])
    )
    constraints.append(
        q_cool_input[1:] == q_cool_input[:-1] + 
        alpha * (p_cool[:-1] * cool_cops[:-1] - q_cool_input[:-1])
    )
    
    # Temperature dynamics with filtered inputs
    constraints.append(
        pred_temp[1:] == (
            pred_temp[:-1] + 
            (q_heat_input[:-1] * conversion) -         # Filtered heating effect
            (q_cool_input[:-1] * conversion) -         # Filtered cooling effect
            (thermal_losses[:-1] * conversion) -       # Thermal losses
            (heating_demand[:-1] * conversion) +       # Heating demand
            (cooling_demand[:-1] * conversion) +       # Cooling demand
            (solar_gains[:-1] * conversion)            # Solar gains
        )
    )
```

## 10. Physical Interpretation and Validation

### 10.1. Energy Balance

The temperature dynamics equation represents an energy balance:

```
Energy Change = Energy In - Energy Out
```

For the thermal mass, this translates to:

```
Temperature Change ∝ (Heating Input + Heat Gains) - (Cooling Extraction + Heat Losses)
```

### 10.2. Physical Validation

To ensure the model is physically correct:

1. When only heating is active (`p_heat > 0, p_cool = 0`), temperature should increase
2. When only cooling is active (`p_heat = 0, p_cool > 0`), temperature should decrease
3. When neither is active, temperature should change based on external factors (losses, gains)

### 10.3. Numerical Validation

Include validation in the code to ensure:

1. The temperature stays within physical bounds
2. Energy conservation is maintained
3. The system responds correctly to different input scenarios

## 11. Edge Cases and Considerations

### 11.1. Simultaneous Heating and Cooling

The mutually exclusive constraint prevents simultaneous heating and cooling, but it's worth validating this in the temperature dynamics.

### 11.2. Deadband Operation

In practice, heating and cooling systems often operate with a "deadband" - a temperature range where neither heating nor cooling is active. This behavior emerges naturally from:

1. Minimum and maximum temperature constraints
2. The optimization objective that minimizes energy use

### 11.3. Temperature Overshooting

To prevent temperature overshooting, especially during mode transitions:

1. Use adequate time resolution in the prediction horizon
2. Consider the thermal inertia of the system
3. Implement anti-cycling constraints

## 12. Performance Considerations

The dual-mode temperature dynamics adds complexity to the optimization problem, but several techniques can help maintain performance:

1. Use warm-starting through parameter updates
2. Cache intermediate calculations
3. Apply sparsity patterns in the constraint matrices
4. Consider problem-specific solver options

## 13. Testing and Validation

The temperature dynamics should be tested with:

1. Synthetic scenarios (heating-only, cooling-only, mixed)
2. Realistic weather and demand profiles
3. Edge cases (extreme temperatures, rapid changes)
4. Comparison with simplified models for validation