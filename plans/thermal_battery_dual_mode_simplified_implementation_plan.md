# Dual-Mode Thermal Battery Implementation Plan

## Overview

This document outlines the implementation plan for adding dual-mode (heating and cooling) capabilities to the EMHASS thermal_battery component. This approach allows the optimizer to automatically select the most efficient mode for each timestep without requiring users to manually configure season-based mode switching.

## 1. Dual-Mode Architecture

The core of this implementation is a dual-mode architecture where:

1. **Both heating and cooling are calculated simultaneously**
2. **The optimizer selects the most cost-effective mode at each timestep**
3. **A single configuration handles both heating and cooling operations year-round**

### 1.1. Configuration Parameters

```json
"thermal_battery": {
  "dual_mode_enabled": true,                // Enable dual-mode operation
  "heat_supply_temperature": 35.0,          // Supply temp for heating mode
  "cool_supply_temperature": 12.0,          // Supply temp for cooling mode
  "heat_carnot_efficiency": 0.4,            // Efficiency for heating
  "cool_carnot_efficiency": 0.45,           // Efficiency for cooling
  "volume": 20.0,
  "start_temperature": 22.0,
  "min_temperatures": [20.0] * 48,          // Lower comfort bound
  "max_temperatures": [26.0] * 48,          // Upper comfort bound
  "u_value": 0.5,
  "envelope_area": 400.0,
  "ventilation_rate": 0.5,
  "heated_volume": 300.0,
  "window_area": 40.0,                      // Optional for solar gains
  "shgc": 0.6,                              // Solar Heat Gain Coefficient
  "internal_gains_factor": 0.7,             // Optional for internal gains
  "latent_cooling_factor": 0.3,             // For dehumidification in cooling
}
```

## 2. Core Implementation Components

### 2.1. Separate Heating and Cooling Variables

Define separate decision variables for heating and cooling operations:

```python
# Power variables
p_heat = cp.Variable(n, name=f"p_heat_{k}")
p_cool = cp.Variable(n, name=f"p_cool_{k}")

# Binary mode indicators
heat_active = cp.Variable(n, boolean=True, name=f"heat_active_{k}")
cool_active = cp.Variable(n, boolean=True, name=f"cool_active_{k}")
```

### 2.2. Mutually Exclusive Operation

Ensure that heating and cooling don't operate simultaneously:

```python
# Constraint to prevent simultaneous heating and cooling
constraints.append(heat_active + cool_active <= 1)

# Link binary variables to power values
constraints.append(p_heat <= heat_active * nominal_power)
constraints.append(p_cool <= cool_active * nominal_power)
```

### 2.3. Dual COP Calculation

Calculate COPs for both heating and cooling modes based on outdoor temperature:

```python
def calculate_cop_dual_mode(
    heat_supply_temperature: float,
    cool_supply_temperature: float,
    heat_carnot_efficiency: float,
    cool_carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate both heating and cooling COPs simultaneously.
    
    For heating: COP = η_carnot × T_supply / (T_supply - T_outdoor)
    For cooling: COP = η_carnot × T_supply / (T_outdoor - T_supply)
    """
    # Implementation with appropriate calculations for both modes
    # ...
    
    return heat_cop, cool_cop
```

### 2.4. Temperature Dynamics with Both Modes

Update the temperature evolution equation to account for both heating and cooling:

```python
# Temperature evolution constraint
constraints.append(
    pred_temp[1:] == (
        pred_temp[:-1] + 
        (p_heat[:-1] * heat_cops[:-1] * conversion) -   # Heating effect (adds heat)
        (p_cool[:-1] * cool_cops[:-1] * conversion) -   # Cooling effect (removes heat)
        (thermal_losses[:-1] * conversion) -            # Thermal losses
        (heating_demand[:-1] * conversion) +            # Heating demand
        (cooling_demand[:-1] * conversion) +            # Cooling demand
        (solar_gains[:-1] * conversion)                 # Solar gains
    )
)
```

### 2.5. Separate Heating and Cooling Demand Calculation

Calculate both heating and cooling demands simultaneously:

```python
def calculate_dual_thermal_demand(
    u_value: float,
    envelope_area: float,
    ventilation_rate: float,
    heated_volume: float,
    indoor_target_temperature: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
    optimization_time_step: int,
    solar_irradiance_forecast: np.ndarray | pd.Series | None = None,
    window_area: float | None = None,
    shgc: float = 0.6,
    internal_gains_forecast: np.ndarray | pd.Series | None = None,
    internal_gains_factor: float = 0.0,
    latent_cooling_factor: float = 0.3,
) -> dict[str, np.ndarray]:
    """
    Calculate both heating and cooling demands simultaneously.
    
    Key differences in calculation:
    - Heating demand = losses - gains (gains reduce heating need)
    - Cooling demand = losses + gains (gains increase cooling need)
    """
    # Implementation with separate heating/cooling calculations
    # ...
    
    return {
        "heating_demand_kwh": heating_demand_kwh,
        "cooling_demand_kwh": cooling_demand_kwh,
        "solar_gains_kwh": solar_gains_kwh,
        # ...other components
    }
```

### 2.6. Enhanced Sensor Publishing

Publish separate sensors for heating and cooling operations:

```python
def _publish_dual_mode_thermal_battery_results(
    self, k, p_heat_vals, p_cool_vals, mode_vals, sens_temps, 
    heat_demand, cool_demand, heat_cops, cool_cops, solar_gains
):
    """Publish dual-mode thermal battery results to Home Assistant."""
    # Publish heating power
    self._publish_sensor(f"p_heat{k}", p_heat_vals, 
                         {"friendly_name": f"Heating Power {k}", 
                          "icon": "mdi:radiator"})
    
    # Publish cooling power
    self._publish_sensor(f"p_cool{k}", p_cool_vals, 
                         {"friendly_name": f"Cooling Power {k}", 
                          "icon": "mdi:snowflake"})
    
    # Publish net power (backward compatibility)
    self._publish_sensor(f"p_deferrable{k}", p_heat_vals - p_cool_vals, 
                         {"friendly_name": f"Net Thermal Power {k}"})
    
    # Publish temperature and other sensors
    # ...
```

## 3. Core Code Changes

### 3.1. Update `_initialize_decision_variables()`

```python
def _initialize_decision_variables(self):
    # ... (existing code)
    
    for k in range(num_def_loads):
        if (
            "def_load_config" in self.optim_conf.keys()
            and len(self.optim_conf["def_load_config"]) > k
            and "thermal_battery" in self.optim_conf["def_load_config"][k]
            and self.optim_conf["def_load_config"][k]["thermal_battery"].get("dual_mode_enabled", True)
        ):
            # Create heating power variable
            p_heat = cp.Variable(self.num_timesteps, name=f"p_heat_{k}")
            self.vars[f"p_heat_{k}"] = p_heat
            
            # Create cooling power variable
            p_cool = cp.Variable(self.num_timesteps, name=f"p_cool_{k}")
            self.vars[f"p_cool_{k}"] = p_cool
            
            # Create binary mode indicators
            heat_active = cp.Variable(self.num_timesteps, boolean=True, name=f"heat_active_{k}")
            self.vars[f"heat_active_{k}"] = heat_active
            
            cool_active = cp.Variable(self.num_timesteps, boolean=True, name=f"cool_active_{k}")
            self.vars[f"cool_active_{k}"] = cool_active
            
            # Link to p_deferrable for backward compatibility
            self.constraints.append(self.vars["p_deferrable"][k] == p_heat - p_cool)
            
            # Enforce mutually exclusive operation
            self.constraints.append(heat_active + cool_active <= 1)
            
            # Link binary variables to power
            nominal_power = self.optim_conf["nominal_power_of_deferrable_loads"][k]
            self.constraints.append(p_heat <= heat_active * nominal_power)
            self.constraints.append(p_cool <= cool_active * nominal_power)
```

### 3.2. Modify `_add_thermal_battery_constraints()`

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    """Handle constraints for thermal battery loads with dual-mode operation."""
    # ... (existing setup)
    
    # Get separate power variables for heating and cooling
    p_heat = self.vars[f"p_heat_{k}"]
    p_cool = self.vars[f"p_cool_{k}"]
    
    # Calculate dual COPs
    heat_cops, cool_cops = calculate_cop_dual_mode(
        heat_supply_temperature=hc["heat_supply_temperature"],
        cool_supply_temperature=hc["cool_supply_temperature"],
        heat_carnot_efficiency=hc["heat_carnot_efficiency"],
        cool_carnot_efficiency=hc["cool_carnot_efficiency"],
        outdoor_temperature_forecast=outdoor_temp_arr
    )
    
    # Calculate dual thermal demands
    thermal_demands = calculate_dual_thermal_demand(
        # ...parameters...
    )
    
    heating_demand = thermal_demands["heating_demand_kwh"]
    cooling_demand = thermal_demands["cooling_demand_kwh"]
    
    # Temperature evolution constraint with both heating and cooling
    constraints.append(
        pred_temp[1:] == (
            pred_temp[:-1] + 
            (p_heat[:-1] * heat_cops[:-1] * conversion) -  # Heating
            (p_cool[:-1] * cool_cops[:-1] * conversion) -  # Cooling
            # ...other terms...
        )
    )
    
    # ... (rest of constraints)
```

## 4. Test Cases

Implement thorough test cases covering:

1. **Dual COP calculation** for various outdoor temperatures
2. **Dual demand calculation** with solar and internal gains
3. **Full optimization** with both heating and cooling scenarios
4. **Sensor publishing** with all new dual-mode sensors

## 5. Documentation

Update `thermal_battery.md` to include:

1. **Introduction to dual-mode operation**
2. **Configuration parameter details**
3. **Example configurations**
4. **Explanation of system behavior**
5. **Sensor information**

## 6. Benefits of Dual-Mode Approach

- **User Convenience**: Single configuration works year-round
- **Optimal Operation**: Always selects most cost-effective mode
- **Better Energy Management**: Takes advantage of variable pricing and solar production
- **Enhanced Visualization**: Rich set of sensors for monitoring and automation

## 7. Implementation Strategy

1. Implement dual COP and demand calculation functions
2. Add separate variables and constraints in optimization
3. Update result extraction and sensor publishing
4. Add thorough documentation and examples
5. Implement test cases for verification