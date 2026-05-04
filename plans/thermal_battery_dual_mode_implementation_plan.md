# Dual-Mode Thermal Battery Implementation Plan

## Overview

This document outlines the implementation plan for adding dual-mode (heating and cooling) capabilities to the EMHASS thermal_battery component. The dual-mode approach allows the optimizer to automatically select the most efficient or cost-effective mode at each timestep, eliminating the need for manual season-based configuration changes.

## 1. Architecture Design

### 1.1. Configuration Parameters

Modify the thermal_battery configuration to include parameters for both heating and cooling operations:

```json
"thermal_battery": {
  "heat_supply_temperature": 35.0,       // Supply temp for heating mode
  "cool_supply_temperature": 12.0,       // Supply temp for cooling mode
  "heat_carnot_efficiency": 0.4,         // Efficiency for heating
  "cool_carnot_efficiency": 0.45,        // Efficiency for cooling
  "volume": 20.0,
  "start_temperature": 22.0,
  "min_temperatures": [20.0] * 48,       // Lower comfort bound
  "max_temperatures": [26.0] * 48,       // Upper comfort bound
  "desired_temperatures": [22.0] * 48,   // Optimal temperature (optional)
  "u_value": 0.5,
  "envelope_area": 400.0,
  "ventilation_rate": 0.5,
  "heated_volume": 300.0,
  "window_area": 40.0,
  "shgc": 0.6,
  "internal_gains_factor": 0.7,
  "min_runtime": 2,                      // Minimum mode runtime (timesteps)
  "transition_cooldown": 1,              // Cooldown between mode switches
  "dual_mode_enabled": true              // Enable dual-mode operation
}
```

### 1.2. Decision Variables

Define separate variables for heating and cooling operations:

```python
# Power variables
p_heat = cp.Variable(n, name=f"p_heat_{k}")
p_cool = cp.Variable(n, name=f"p_cool_{k}")

# Binary mode indicators
heat_active = cp.Variable(n, boolean=True, name=f"heat_active_{k}")
cool_active = cp.Variable(n, boolean=True, name=f"cool_active_{k}")
```

## 2. Core Function Changes

### 2.1. Enhanced COP Calculation

Modify `utils.py` to support dual COP calculations:

```python
def calculate_cop_dual_mode(
    heat_supply_temperature: float,
    cool_supply_temperature: float,
    heat_carnot_efficiency: float,
    cool_carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate COPs for both heating and cooling modes simultaneously.
    
    Returns:
        tuple: (heating_cop_array, cooling_cop_array)
    """
    # Convert to numpy array if pandas Series
    if isinstance(outdoor_temperature_forecast, pd.Series):
        outdoor_temps = outdoor_temperature_forecast.values
    else:
        outdoor_temps = np.asarray(outdoor_temperature_forecast)
    
    # Convert temperatures to Kelvin
    heat_supply_kelvin = heat_supply_temperature + 273.15
    cool_supply_kelvin = cool_supply_temperature + 273.15
    outdoor_kelvin = outdoor_temps + 273.15
    
    # Calculate heating COP
    heat_temp_diff = heat_supply_kelvin - outdoor_kelvin
    heat_cop = np.ones_like(outdoor_kelvin)  # Default to 1.0
    valid_heat = heat_temp_diff > 0
    if np.any(valid_heat):
        heat_cop[valid_heat] = heat_carnot_efficiency * heat_supply_kelvin / heat_temp_diff[valid_heat]
    heat_cop = np.clip(heat_cop, 1.0, 8.0)
    
    # Calculate cooling COP
    cool_temp_diff = outdoor_kelvin - cool_supply_kelvin
    cool_cop = np.ones_like(outdoor_kelvin)  # Default to 1.0
    valid_cool = cool_temp_diff > 0
    if np.any(valid_cool):
        cool_cop[valid_cool] = cool_carnot_efficiency * cool_supply_kelvin / cool_temp_diff[valid_cool]
    cool_cop = np.clip(cool_cop, 1.0, 10.0)
    
    return heat_cop, cool_cop
```

### 2.2. Dual Thermal Demand Calculation

Modify `utils.py` to calculate both heating and cooling demands:

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
) -> dict[str, np.ndarray]:
    """
    Calculate heating and cooling demand components simultaneously.
    """
    # Convert outdoor temperature to numpy array
    outdoor_temps = (
        outdoor_temperature_forecast.values
        if isinstance(outdoor_temperature_forecast, pd.Series)
        else np.asarray(outdoor_temperature_forecast)
    )
    
    # Calculate heating and cooling temperature differences
    heating_temp_diff = indoor_target_temperature - outdoor_temps
    cooling_temp_diff = outdoor_temps - indoor_target_temperature
    
    # Apply non-negativity constraints
    heating_temp_diff = np.maximum(heating_temp_diff, 0.0)
    cooling_temp_diff = np.maximum(cooling_temp_diff, 0.0)
    
    # Transmission losses/gains
    heating_transmission_kw = u_value * envelope_area * heating_temp_diff / 1000.0
    cooling_transmission_kw = u_value * envelope_area * cooling_temp_diff / 1000.0
    
    # Ventilation losses/gains
    air_density = 1.2  # kg/m³
    air_heat_capacity = 1.005  # kJ/(kg·K)
    heating_ventilation_kw = (
        ventilation_rate * heated_volume * air_density * air_heat_capacity * heating_temp_diff / 3600.0
    )
    cooling_ventilation_kw = (
        ventilation_rate * heated_volume * air_density * air_heat_capacity * cooling_temp_diff / 3600.0
    )
    
    # Total thermal loads
    heating_load_kw = heating_transmission_kw + heating_ventilation_kw
    cooling_load_kw = cooling_transmission_kw + cooling_ventilation_kw
    
    # Solar gains calculation
    solar_gains_kw = np.zeros_like(outdoor_temps)
    if solar_irradiance_forecast is not None and window_area is not None:
        solar_irradiance = (
            solar_irradiance_forecast.values
            if isinstance(solar_irradiance_forecast, pd.Series)
            else np.asarray(solar_irradiance_forecast)
        ).reshape(-1)
        
        window_projection_factor = 0.3
        solar_gains_kw = window_area * shgc * solar_irradiance * window_projection_factor / 1000.0
    
    # Internal gains calculation
    internal_gains_kw = np.zeros_like(outdoor_temps)
    if internal_gains_forecast is not None and internal_gains_factor > 0:
        internal_gains = (
            internal_gains_forecast.values
            if isinstance(internal_gains_forecast, pd.Series)
            else np.asarray(internal_gains_forecast)
        ).reshape(-1)
        
        internal_gains_kw = internal_gains * internal_gains_factor / 1000.0
    
    # Convert to kWh
    hours = optimization_time_step / 60.0
    heating_load_kwh = heating_load_kw * hours
    cooling_load_kwh = cooling_load_kw * hours
    solar_gains_kwh = solar_gains_kw * hours
    internal_gains_kwh = internal_gains_kw * hours
    
    # Final demand calculations
    # For heating: demand = load - gains (gains reduce heating need)
    # For cooling: demand = load + gains (gains increase cooling need)
    heating_demand_kwh = np.maximum(heating_load_kwh - solar_gains_kwh - internal_gains_kwh, 0.0)
    cooling_demand_kwh = np.maximum(cooling_load_kwh + solar_gains_kwh + internal_gains_kwh, 0.0)
    
    return {
        "heating_load_kwh": heating_load_kwh,
        "cooling_load_kwh": cooling_load_kwh,
        "solar_gains_kwh": solar_gains_kwh,
        "internal_gains_kwh": internal_gains_kwh,
        "heating_demand_kwh": heating_demand_kwh,
        "cooling_demand_kwh": cooling_demand_kwh,
    }
```

## 3. Optimization Module Changes

### 3.1. Constraint Generation

Update `_add_thermal_battery_constraints()` in `optimization.py` to support dual-mode operation:

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    """
    Handle constraints for thermal battery loads with dual-mode operation.
    """
    # Basic setup - extract config, etc.
    def_load_config = self.optim_conf["def_load_config"][k]
    hc = def_load_config["thermal_battery"]
    required_len = self.num_timesteps
    
    # Structural parameters
    volume = hc["volume"]
    min_temperatures_list = hc["min_temperatures"]
    max_temperatures_list = hc["max_temperatures"]
    desired_temperatures_list = hc.get("desired_temperatures", [])
    
    # Check if dual-mode is enabled (default to true)
    dual_mode_enabled = hc.get("dual_mode_enabled", True)
    
    # Get mode-specific parameters
    heat_supply_temp = hc.get("heat_supply_temperature", 35.0)
    cool_supply_temp = hc.get("cool_supply_temperature", 12.0)
    heat_efficiency = hc.get("heat_carnot_efficiency", 0.4)
    cool_efficiency = hc.get("cool_carnot_efficiency", 0.45)
    min_runtime = hc.get("min_runtime", 2)
    transition_cooldown = hc.get("transition_cooldown", 1)
    
    # Create decision variables
    if dual_mode_enabled:
        # Create separate heating and cooling power variables
        p_heat = cp.Variable(required_len, name=f"p_heat_{k}")
        p_cool = cp.Variable(required_len, name=f"p_cool_{k}")
        
        # Create binary mode indicators
        heat_active = cp.Variable(required_len, boolean=True, name=f"heat_active_{k}")
        cool_active = cp.Variable(required_len, boolean=True, name=f"cool_active_{k}")
        
        # Store in class variables
        self.vars[f"p_heat_{k}"] = p_heat
        self.vars[f"p_cool_{k}"] = p_cool
        self.vars[f"heat_active_{k}"] = heat_active
        self.vars[f"cool_active_{k}"] = cool_active
        
        # For backward compatibility, also define p_deferrable as the net effect
        p_deferrable = self.vars["p_deferrable"][k]
        
        # Add constraint linking p_deferrable to p_heat and p_cool
        # Using opposite signs: p_deferrable = p_heat - p_cool
        constraints.append(p_deferrable == p_heat - p_cool)
    else:
        # Use traditional single-mode operation
        p_deferrable = self.vars["p_deferrable"][k]
        p_heat = p_deferrable  # p_heat is p_deferrable
        p_cool = cp.Parameter(required_len, value=np.zeros(required_len))  # p_cool is zero
    
    # Get thermal parameters
    outdoor_temp_arr = self._get_clean_outdoor_temp(data_opt, required_len)
    
    # Calculate COPs
    heat_cop, cool_cop = utils.calculate_cop_dual_mode(
        heat_supply_temperature=heat_supply_temp,
        cool_supply_temperature=cool_supply_temp,
        heat_carnot_efficiency=heat_efficiency,
        cool_carnot_efficiency=cool_efficiency,
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
    )
    
    # Calculate thermal demands
    thermal_demands = utils.calculate_dual_thermal_demand(
        u_value=hc["u_value"],
        envelope_area=hc["envelope_area"],
        ventilation_rate=hc["ventilation_rate"],
        heated_volume=hc["heated_volume"],
        indoor_target_temperature=hc.get(
            "indoor_target_temperature", 
            min_temperatures_list[0] if min_temperatures_list else 20.0
        ),
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
        optimization_time_step=int(self.freq.total_seconds() / 60),
        solar_irradiance_forecast=data_opt.get("ghi"),
        window_area=hc.get("window_area"),
        shgc=hc.get("shgc", 0.6),
        internal_gains_forecast=p_load if hc.get("internal_gains_factor", 0.0) > 0 else None,
        internal_gains_factor=hc.get("internal_gains_factor", 0.0),
    )
    
    # Extract demand and gains arrays
    heating_demand = thermal_demands["heating_demand_kwh"]
    cooling_demand = thermal_demands["cooling_demand_kwh"]
    solar_gains = thermal_demands["solar_gains_kwh"]
    
    # Thermal conversion factors
    p_concr = 2400
    c_concr = 0.88
    loss = 0.045
    conversion = 3600 / (p_concr * c_concr * volume)
    
    # Losses calculation
    start_temp_float = float(hc.get("start_temperature", 20.0))
    losses = utils.calculate_thermal_loss_signed(
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
        indoor_temperature=start_temp_float,
        base_loss=loss,
    )
    
    # Temperature variable
    pred_temp = cp.Variable(required_len, name=f"temp_load_{k}")
    constraints.append(pred_temp[0] == start_temp_float)
    
    # Temperature dynamics with both heating and cooling effects
    constraints.append(
        pred_temp[1:] == (
            pred_temp[:-1] 
            + (p_heat[:-1] * heat_cop[:-1] * 1.0 * conversion)  # Heating effect
            - (p_cool[:-1] * cool_cop[:-1] * 1.0 * conversion)  # Cooling effect
            - (losses[:-1] * conversion)                        # Thermal losses
            - (heating_demand[:-1] * conversion)                # Heating demand
            + (cooling_demand[:-1] * conversion)                # Cooling demand (adds heat)
            + (solar_gains[:-1] * conversion)                   # Solar gains
        )
    )
    
    # Temperature bounds
    min_temperatures = self._pad_temp_array(min_temperatures_list, required_len, 18.0)
    max_temperatures = self._pad_temp_array(max_temperatures_list, required_len, 26.0)
    constraints.append(pred_temp >= min_temperatures)
    constraints.append(pred_temp <= max_temperatures)
    
    # If dual mode is enabled, add mode-specific constraints
    if dual_mode_enabled:
        # Nominal power for each mode
        nominal_power = self.optim_conf["nominal_power_of_deferrable_loads"][k]
        
        # Semi-continuous constraints for each mode
        constraints.append(p_heat <= heat_active * nominal_power)
        constraints.append(p_cool <= cool_active * nominal_power)
        
        # Mutual exclusivity constraint - can't heat and cool at the same time
        constraints.append(heat_active + cool_active <= 1)
        
        # Anti-cycling constraints if min_runtime > 1
        if min_runtime > 1:
            for t in range(1, required_len):
                # For each mode, if active at t and wasn't active at t-1, 
                # must remain active for min_runtime steps
                for i in range(1, min(min_runtime, required_len - t)):
                    constraints.append(
                        heat_active[t] - heat_active[t-1] <= heat_active[t + i]
                    )
                    constraints.append(
                        cool_active[t] - cool_active[t-1] <= cool_active[t + i]
                    )
        
        # Mode transition cooldown if specified
        if transition_cooldown > 0:
            for t in range(transition_cooldown, required_len):
                # Can't activate heating if cooling was active in the cooldown period
                cooling_in_cooldown = sum(cool_active[t-i] for i in range(1, transition_cooldown+1))
                constraints.append(heat_active[t] + cooling_in_cooldown <= 1)
                
                # Can't activate cooling if heating was active in the cooldown period
                heating_in_cooldown = sum(heat_active[t-i] for i in range(1, transition_cooldown+1))
                constraints.append(cool_active[t] + heating_in_cooldown <= 1)
    
    # Return predicted temperature and thermal demands
    return pred_temp, heating_demand, cooling_demand, solar_gains
```

### 3.2. Objective Function Adjustment

Update `_build_objective_function()` to account for both heating and cooling costs:

```python
def _build_objective_function(self):
    # ... (existing code)
    
    # Deferrable loads cost calculation
    for k in range(num_def_loads):
        if (
            "def_load_config" in self.optim_conf.keys()
            and len(self.optim_conf["def_load_config"]) > k
            and "thermal_battery" in self.optim_conf["def_load_config"][k]
        ):
            # Check if dual mode is enabled
            dual_mode = self.optim_conf["def_load_config"][k]["thermal_battery"].get("dual_mode_enabled", True)
            
            if dual_mode:
                # Add separate costs for heating and cooling
                p_heat = self.vars[f"p_heat_{k}"]
                p_cool = self.vars[f"p_cool_{k}"]
                
                # Get heating and cooling costs
                heating_cost = cp.sum(load_cost * p_heat)
                cooling_cost = cp.sum(load_cost * p_cool)
                
                # Add to total cost
                total_cost += heating_cost + cooling_cost
            else:
                # Traditional single-mode cost
                p_deferrable = self.vars["p_deferrable"][k]
                total_cost += cp.sum(load_cost * p_deferrable)
        else:
            # ... (existing non-thermal battery code)
    
    # ... (existing code)
```

## 4. Results and Sensor Publishing

### 4.1. Building Results DataFrame

Update `_build_results_dataframe()` to include both heating and cooling variables:

```python
def _build_results_dataframe(self):
    # ... (existing code)
    
    for k in range(num_def_loads):
        # Add traditional p_deferrable for backward compatibility
        p_def = get_val(self.vars["p_deferrable"][k])
        df_results[f'p_deferrable{k}'] = p_def
        
        # For thermal batteries with dual mode, add separate heating and cooling variables
        if (
            "def_load_config" in self.optim_conf.keys()
            and len(self.optim_conf["def_load_config"]) > k
            and "thermal_battery" in self.optim_conf["def_load_config"][k]
        ):
            # Check if dual mode is enabled
            dual_mode = self.optim_conf["def_load_config"][k]["thermal_battery"].get("dual_mode_enabled", True)
            
            if dual_mode:
                # Add separate heating and cooling variables
                p_heat = get_val(self.vars[f"p_heat_{k}"])
                p_cool = get_val(self.vars[f"p_cool_{k}"])
                heat_active = get_val(self.vars[f"heat_active_{k}"])
                cool_active = get_val(self.vars[f"cool_active_{k}"])
                
                df_results[f'p_heat{k}'] = p_heat
                df_results[f'p_cool{k}'] = p_cool
                df_results[f'heat_active{k}'] = heat_active
                df_results[f'cool_active{k}'] = cool_active
            
            # Add temperature predictions
            pred_temp = get_val(self.vars[f"temp_load_{k}"])
            df_results[f'temp_predicted{k}'] = pred_temp
    
    # ... (existing code)
```

### 4.2. Sensor Publishing in Web Server

Update the web server to publish dual-mode thermal battery sensors:

```python
def _publish_dual_mode_thermal_battery_results(self, k, p_heat_vals, p_cool_vals, 
                                               sens_temps, heat_demand, cool_demand, 
                                               solar_gains, q_heat_inputs=None, q_cool_inputs=None):
    """Publish dual-mode thermal battery results to Home Assistant"""
    # Common attributes for all thermal battery sensors
    common_attrs = {
        "thermal_battery": "true",
        "dual_mode": "true",
    }
    
    # Publish heating power schedule
    sensor_name = f"p_heat{k}"
    friendly_name = f"Heating Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "icon": "mdi:radiator",
    }
    self._publish_sensor(sensor_name, p_heat_vals, attrs)
    
    # Publish cooling power schedule
    sensor_name = f"p_cool{k}"
    friendly_name = f"Cooling Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "icon": "mdi:snowflake",
    }
    self._publish_sensor(sensor_name, p_cool_vals, attrs)
    
    # Publish net power for backward compatibility
    sensor_name = f"p_deferrable{k}"
    friendly_name = f"Net Thermal Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "icon": "mdi:flash",
    }
    self._publish_sensor(sensor_name, p_heat_vals - p_cool_vals, attrs)
    
    # Publish predicted temperature
    sensor_name = f"temp_predicted{k}"
    friendly_name = f"Predicted Temperature {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "°C",
        "icon": "mdi:thermometer",
    }
    self._publish_sensor(sensor_name, sens_temps, attrs)
    
    # Publish heating demand
    sensor_name = f"heating_demand{k}"
    friendly_name = f"Heating Demand {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "icon": "mdi:radiator",
    }
    self._publish_sensor(sensor_name, heat_demand, attrs)
    
    # Publish cooling demand
    sensor_name = f"cooling_demand{k}"
    friendly_name = f"Cooling Demand {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "icon": "mdi:snowflake",
    }
    self._publish_sensor(sensor_name, cool_demand, attrs)
    
    # Publish solar gains
    sensor_name = f"solar_gains{k}"
    friendly_name = f"Solar Heat Gains {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "icon": "mdi:weather-sunny",
    }
    self._publish_sensor(sensor_name, solar_gains, attrs)
    
    # Publish filtered heat inputs if thermal inertia is enabled
    if q_heat_inputs is not None:
        sensor_name = f"q_input_heat{k}"
        friendly_name = f"Heating Thermal Input {k}"
        attrs = {
            **common_attrs,
            "friendly_name": friendly_name,
            "unit_of_measurement": "kWh",
            "icon": "mdi:radiator",
        }
        self._publish_sensor(sensor_name, q_heat_inputs, attrs)
    
    # Publish filtered cool inputs if thermal inertia is enabled
    if q_cool_inputs is not None:
        sensor_name = f"q_input_cool{k}"
        friendly_name = f"Cooling Thermal Input {k}"
        attrs = {
            **common_attrs,
            "friendly_name": friendly_name,
            "unit_of_measurement": "kWh",
            "icon": "mdi:snowflake",
        }
        self._publish_sensor(sensor_name, q_cool_inputs, attrs)
```

## 5. Documentation Updates

The documentation in `thermal_battery.md` should be extensively updated to explain:

1. The dual-mode architecture
2. New configuration parameters for heating and cooling
3. Anti-cycling protection
4. Sensor naming and attributes
5. Example configurations
6. Performance considerations
7. Troubleshooting tips

## 6. Testing

Create comprehensive tests for:

1. COP calculation for both modes
2. Dual demand calculations
3. Optimization with various scenarios
4. Anti-cycling constraints
5. Mutual exclusivity of modes
6. Sensor publishing
7. Performance benchmarks

## 7. Implementation Roadmap

1. **Phase 1**: Implement core dual COP and demand functions
2. **Phase 2**: Update the thermal battery constraints with dual-mode logic
3. **Phase 3**: Add anti-cycling protection
4. **Phase 4**: Update results and sensor publishing
5. **Phase 5**: Comprehensive documentation
6. **Phase 6**: Testing and validation

## 8. Backward Compatibility

To maintain backward compatibility:

1. Default `dual_mode_enabled` to `true`
2. Continue providing `p_deferrable{k}` sensors
3. Map traditional parameters to dual-mode equivalents when not specified:
   - `supply_temperature` → `heat_supply_temperature`
   - `carnot_efficiency` → `heat_carnot_efficiency`