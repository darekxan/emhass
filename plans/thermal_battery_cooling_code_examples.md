# GSHP Active Cooling Support Code Examples

This document contains code snippets that demonstrate the key modifications required to implement GSHP active cooling support in the thermal_battery component. These examples show how the existing functions would need to be modified to support cooling mode.

## 1. Updating `calculate_cop_heatpump()`

```python
def calculate_cop_heatpump(
    supply_temperature: float,
    carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
    mode: str = "heat",
) -> np.ndarray:
    """
    Calculate heat pump Coefficient of Performance (COP) for each timestep in the prediction horizon.
    
    For heating mode: COP = η_carnot × T_supply_K / (T_supply_K - T_outdoor_K)
    For cooling mode: COP = η_carnot × T_supply_K / (T_outdoor_K - T_supply_K)
    
    Where temperatures are converted to Kelvin (K = °C + 273.15).
    
    :param supply_temperature: The heat pump supply temperature in degrees Celsius
    :param carnot_efficiency: Real-world efficiency factor as fraction of ideal Carnot cycle
    :param outdoor_temperature_forecast: Array of outdoor temperature forecasts in degrees Celsius
    :param mode: Operating mode, either "heat" (default) or "cool"
    :return: Array of COP values for each timestep
    """
    # Validate mode
    if mode not in ["heat", "cool"]:
        raise ValueError(f"Mode must be 'heat' or 'cool', got '{mode}'")
        
    # Convert to numpy array if pandas Series
    if isinstance(outdoor_temperature_forecast, pd.Series):
        outdoor_temps = outdoor_temperature_forecast.values
    else:
        outdoor_temps = np.asarray(outdoor_temperature_forecast)

    # Convert temperatures from Celsius to Kelvin for Carnot formula
    supply_temperature_kelvin = supply_temperature + 273.15
    outdoor_temperature_kelvin = outdoor_temps + 273.15

    # Calculate temperature difference based on mode
    if mode == "heat":
        # For heating, supply temperature should be higher than outdoor temperature
        temperature_diff = supply_temperature_kelvin - outdoor_temperature_kelvin
        
        # Check for non-physical scenarios in heating mode
        if np.any(temperature_diff <= 0):
            logger = logging.getLogger(__name__)
            num_invalid = np.sum(temperature_diff <= 0)
            invalid_indices = np.nonzero(temperature_diff <= 0)[0]
            logger.warning(
                f"Heating COP calculation: {num_invalid} timestep(s) have outdoor temperature >= supply temperature. "
                f"This is non-physical for heating mode. Indices: {invalid_indices.tolist()[:5]}{'...' if len(invalid_indices) > 5 else ''}. "
                f"Supply temp: {supply_temperature:.1f}°C. Setting COP to 1.0 (direct electric) for these periods."
            )
    else:  # cooling mode
        # For cooling, outdoor temperature should be higher than supply temperature
        temperature_diff = outdoor_temperature_kelvin - supply_temperature_kelvin
        
        # Check for non-physical scenarios in cooling mode
        if np.any(temperature_diff <= 0):
            logger = logging.getLogger(__name__)
            num_invalid = np.sum(temperature_diff <= 0)
            invalid_indices = np.nonzero(temperature_diff <= 0)[0]
            logger.warning(
                f"Cooling COP calculation: {num_invalid} timestep(s) have outdoor temperature <= supply temperature. "
                f"This is non-physical for cooling mode. Indices: {invalid_indices.tolist()[:5]}{'...' if len(invalid_indices) > 5 else ''}. "
                f"Supply temp: {supply_temperature:.1f}°C. Setting COP to 1.0 (direct electric) for these periods."
            )

    # Vectorized Carnot-based COP calculation
    # Avoid division by zero by using a mask for valid cases
    cop_values = np.ones_like(outdoor_temperature_kelvin)  # Default to 1.0 everywhere
    valid_mask = temperature_diff > 0
    
    if np.any(valid_mask):
        cop_values[valid_mask] = (
            carnot_efficiency * supply_temperature_kelvin / temperature_diff[valid_mask]
        )

    # Apply realistic bounds: minimum 1.0, maximum depends on mode
    # Cooling COPs typically can be higher than heating COPs
    max_cop = 10.0 if mode == "cool" else 8.0
    cop_values = np.clip(cop_values, 1.0, max_cop)

    return cop_values
```

## 2. Implementing Cooling Demand Calculation

```python
def calculate_heating_demand_physics_components(
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
    mode: str = "heat",
) -> dict[str, np.ndarray]:
    """
    Calculate physics-based thermal demand components per timestep.
    Supports both heating and cooling modes.
    
    In heating mode:
    - Temperature difference: indoor_temp - outdoor_temp (when indoor > outdoor)
    - Solar and internal gains reduce heating demand
    
    In cooling mode:
    - Temperature difference: outdoor_temp - indoor_temp (when outdoor > indoor)
    - Solar and internal gains increase cooling demand
    
    :param mode: Operating mode, either "heat" (default) or "cool"
    :return: Dictionary with component arrays in kWh per timestep
    """
    # Validate mode
    if mode not in ["heat", "cool"]:
        raise ValueError(f"Mode must be 'heat' or 'cool', got '{mode}'")
    
    # Convert outdoor temperature forecast to numpy array if pandas Series
    outdoor_temps = (
        outdoor_temperature_forecast.values
        if isinstance(outdoor_temperature_forecast, pd.Series)
        else np.asarray(outdoor_temperature_forecast)
    )

    # Calculate temperature difference based on mode
    if mode == "heat":
        # For heating, we need indoor > outdoor
        temp_diff = indoor_target_temperature - outdoor_temps
        temp_diff = np.maximum(temp_diff, 0.0)
    else:  # cooling mode
        # For cooling, we need outdoor > indoor
        temp_diff = outdoor_temps - indoor_target_temperature
        temp_diff = np.maximum(temp_diff, 0.0)

    # Transmission losses: Q_trans = U * A * ΔT (W to kW)
    transmission_load_kw = u_value * envelope_area * temp_diff / 1000.0

    # Ventilation losses: Q_vent = V * ρ * c * n * ΔT / 3600
    air_density = 1.2  # kg/m³ at 20°C
    air_heat_capacity = 1.005  # kJ/(kg·K)
    ventilation_load_kw = (
        ventilation_rate * heated_volume * air_density * air_heat_capacity * temp_diff / 3600.0
    )

    # Total heat load in kW before gains
    total_load_kw = transmission_load_kw + ventilation_load_kw

    # Initialize solar gains
    solar_gains_kw = np.zeros_like(total_load_kw)

    # Calculate solar gains if irradiance and window area are provided
    if solar_irradiance_forecast is not None and window_area is not None:
        # Convert solar irradiance to numpy array
        solar_irradiance = (
            solar_irradiance_forecast.values
            if isinstance(solar_irradiance_forecast, pd.Series)
            else np.asarray(solar_irradiance_forecast)
        )
        solar_irradiance = np.asarray(solar_irradiance).reshape(-1)
        
        # Validate lengths match
        if len(solar_irradiance) != len(outdoor_temps):
            raise ValueError(
                f"solar_irradiance_forecast length ({len(solar_irradiance)}) must match "
                f"outdoor_temperature_forecast length ({len(outdoor_temps)})"
            )

        # Solar gains with window projection factor
        window_projection_factor = 0.3
        solar_gains_kw = window_area * shgc * solar_irradiance * window_projection_factor / 1000.0

    # Validate internal_gains_factor is in expected range [0, 1]
    if internal_gains_factor < 0 or internal_gains_factor > 1:
        raise ValueError(
            f"internal_gains_factor must be between 0 and 1, got {internal_gains_factor}"
        )

    # Initialize internal gains
    internal_gains_kw = np.zeros_like(total_load_kw)

    # Calculate internal gains from electrical load if provided and applicable
    if internal_gains_forecast is not None and internal_gains_factor > 0:
        # Convert internal gains forecast to numpy array
        internal_gains = (
            internal_gains_forecast.values
            if isinstance(internal_gains_forecast, pd.Series)
            else np.asarray(internal_gains_forecast)
        )
        internal_gains = np.asarray(internal_gains).reshape(-1)
        
        # Validate lengths match
        if len(internal_gains) != len(outdoor_temps):
            raise ValueError(
                f"internal_gains_forecast length ({len(internal_gains)}) must match "
                f"outdoor_temperature_forecast length ({len(outdoor_temps)})"
            )

        # Convert W to kW and apply gain factor
        internal_gains_kw = internal_gains * internal_gains_factor / 1000.0

    # Compute time interval in hours for kWh calculation
    hours = optimization_time_step / 60.0

    # Convert kW to kWh
    heat_loss_kwh = total_load_kw * hours
    solar_gains_kwh = solar_gains_kw * hours
    internal_gains_kwh = internal_gains_kw * hours

    # Calculate net thermal demand based on mode
    if mode == "heat":
        # For heating, gains reduce demand
        thermal_demand_kwh = heat_loss_kwh - solar_gains_kwh - internal_gains_kwh
        # Ensure demand is not negative (no active cooling in heating mode)
        thermal_demand_kwh = np.maximum(thermal_demand_kwh, 0.0)
    else:  # cooling mode
        # For cooling, gains increase demand
        thermal_demand_kwh = heat_loss_kwh + solar_gains_kwh + internal_gains_kwh
        # Ensure demand is not negative (no active heating in cooling mode)
        thermal_demand_kwh = np.maximum(thermal_demand_kwh, 0.0)

    # Return all components
    return {
        "heat_loss_kwh": heat_loss_kwh,
        "solar_gains_kwh": solar_gains_kwh,
        "internal_gains_kwh": internal_gains_kwh,
        "thermal_demand_kwh": thermal_demand_kwh,
    }
```

## 3. Updating Thermal Battery Constraints for Cooling Mode

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    """
    Handle constraints for thermal battery loads (Vectorized, Legacy Match).
    Supports both heating and cooling modes via the 'sense' parameter.
    """
    p_deferrable = self.vars["p_deferrable"][k]

    def_load_config = self.optim_conf["def_load_config"][k]
    hc = def_load_config["thermal_battery"]
    required_len = self.num_timesteps
    
    # Get sense parameter (default to "heat" for backward compatibility)
    sense = hc.get("sense", "heat")
    
    # Validate sense parameter
    if sense not in ["heat", "cool"]:
        raise ValueError(f"Load {k}: thermal_battery sense must be 'heat' or 'cool', got '{sense}'")
    
    # Set sense coefficient for calculations (1 for heating, -1 for cooling)
    sense_coeff = 1 if sense == "heat" else -1

    # Structural parameters
    supply_temperature = hc["supply_temperature"]
    volume = hc["volume"]
    min_temperatures_list = hc["min_temperatures"]
    max_temperatures_list = hc["max_temperatures"]

    if not min_temperatures_list:
        raise ValueError(f"Load {k}: thermal_battery requires non-empty 'min_temperatures'")
    if not max_temperatures_list:
        raise ValueError(f"Load {k}: thermal_battery requires non-empty 'max_temperatures'")

    p_concr = 2400
    c_concr = 0.88
    loss = 0.045
    conversion = 3600 / (p_concr * c_concr * volume)

    # Use parameterized values if available
    if k in self.param_thermal:
        params = self.param_thermal[k]
        start_temperature = params["start_temp"]
        heatpump_cops = params["heatpump_cops"]
        thermal_losses = params["thermal_losses"]
        heating_demand = params["heating_demand"]
        solar_gains = params["solar_gains"]
        min_temps_param = params["min_temps"]
        max_temps_param = params["max_temps"]

        # Initialize parameter values
        outdoor_temp_arr = self._get_clean_outdoor_temp(data_opt, required_len)
        params["outdoor_temp"].value = outdoor_temp_arr
        start_temp_float = float(params["start_temp"].value)

        # Compute and set COP values with the appropriate mode
        cops = utils.calculate_cop_heatpump(
            supply_temperature=supply_temperature,
            carnot_efficiency=hc.get("carnot_efficiency", 0.4),
            outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
            mode=sense,  # Pass the mode to COP calculation
        )
        params["heatpump_cops"].value = np.array(cops[:required_len])

        # Calculate thermal losses
        losses = utils.calculate_thermal_loss_signed(
            outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
            indoor_temperature=start_temp_float,
            base_loss=loss,
        )
        params["thermal_losses"].value = np.array(losses[:required_len])

        # Compute thermal demand (heating or cooling)
        if all(
            key in hc
            for key in ["u_value", "envelope_area", "ventilation_rate", "heated_volume"]
        ):
            indoor_target_temp = hc.get(
                "indoor_target_temperature",
                min_temperatures_list[0] if min_temperatures_list else 20.0,
            )
            window_area = hc.get("window_area", None)
            shgc = hc.get("shgc", 0.6)
            internal_gains_factor = hc.get("internal_gains_factor", 0.0)
            internal_gains_forecast = p_load if internal_gains_factor > 0 else None
            
            solar_irradiance = None
            if "ghi" in data_opt.columns and window_area is not None:
                vals = data_opt["ghi"].values
                if len(vals) < required_len:
                    vals = np.concatenate((vals, np.zeros(required_len - len(vals))))
                solar_irradiance = vals[:required_len]

            # Calculate thermal demand with the appropriate mode
            heat_balance = utils.calculate_heating_demand_physics_components(
                u_value=hc["u_value"],
                envelope_area=hc["envelope_area"],
                ventilation_rate=hc["ventilation_rate"],
                heated_volume=hc["heated_volume"],
                indoor_target_temperature=indoor_target_temp,
                outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
                optimization_time_step=int(self.freq.total_seconds() / 60),
                solar_irradiance_forecast=solar_irradiance,
                window_area=window_area,
                shgc=shgc,
                internal_gains_forecast=internal_gains_forecast,
                internal_gains_factor=internal_gains_factor,
                mode=sense,  # Pass the mode to demand calculation
            )
            
            # Store demand and gains
            # In heating mode: effective_demand = heat_loss - gains
            # In cooling mode: effective_demand = heat_loss + gains
            params["heating_demand"].value = np.array(heat_balance["thermal_demand_kwh"][:required_len])
            params["solar_gains"].value = np.array(heat_balance["solar_gains_kwh"][:required_len])
            
    # ... (rest of the function with temperature dynamics constraints) ...
    
    # Temperature Evolution Constraint - modified for sense coefficient
    constraints.append(
        pred_temp[1:] == (
            pred_temp[:-1] 
            + (sense_coeff * p_deferrable[:-1] * heatpump_cops[:-1] * 1.0 * conversion) 
            - (thermal_losses[:-1] * conversion)
            - (sense_coeff * heating_demand[:-1] * conversion)
            + (solar_gains[:-1] * conversion)
        )
    )

    # Temperature Min/Max Constraints - unchanged as these are comfort bounds
    # regardless of heating/cooling mode
    constraints.append(pred_temp >= min_temperatures)
    constraints.append(pred_temp <= max_temperatures)

    # ... (rest of the function) ...
```

## 4. Documentation Sample (thermal_battery.md)

```markdown
## Cooling Mode Support

The thermal_battery model now supports cooling operation for heat pumps that can operate in both heating and cooling modes, such as ground source heat pumps (GSHP).

### Enabling Cooling Mode

To configure a thermal battery for cooling operation, add the `sense` parameter with value `"cool"`:

```json
"def_load_config": [
  {
    "thermal_battery": {
      "sense": "cool",
      "supply_temperature": 12.0,
      "volume": 20.0,
      "start_temperature": 25.0,
      "min_temperatures": [20.0] * 48,
      "max_temperatures": [26.0] * 48,
      "carnot_efficiency": 0.45,
      "u_value": 0.5,
      "envelope_area": 400.0,
      "ventilation_rate": 0.5,
      "heated_volume": 300.0
    }
  }
]
```

### Cooling Mode Configuration Notes

When operating in cooling mode:

1. **supply_temperature**: Set this to your heat pump's cold water supply temperature (typically 7-15°C)
2. **min_temperatures**: Lower comfort bound (temperature should not drop below this)
3. **max_temperatures**: Upper comfort bound (temperature that will trigger cooling)
4. **carnot_efficiency**: Cooling operation often has higher efficiency than heating

### How Cooling Mode Works

In cooling mode:
- The optimizer will run the heat pump to keep the building below max_temperature
- When outdoor temperature is higher than indoor, the building gains heat
- The heat pump removes heat from the building and rejects it outdoors
- COP is calculated based on the cooling cycle formula
- Solar gains and internal heat gains increase cooling demand

The optimization will determine the best times to run cooling based on:
- Electricity pricing
- Heat pump efficiency (COP)
- Building thermal gains
- Solar PV production (to use excess solar for cooling)