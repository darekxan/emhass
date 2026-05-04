# Implementing Separate Heating and Cooling Demand Calculations

This document details the implementation of separate heating and cooling demand calculations for the dual-mode thermal battery component in EMHASS.

## 1. Understanding Building Thermal Demand

### 1.1. Heating vs. Cooling Demand

Buildings experience two distinct types of thermal demand:

1. **Heating Demand**: Required when indoor temperature falls below the desired setpoint, typically during cold weather
2. **Cooling Demand**: Required when indoor temperature rises above the desired setpoint, typically during hot weather

These demands are fundamentally different in their calculation and behavior:

| Aspect | Heating Demand | Cooling Demand |
|--------|---------------|---------------|
| Temperature Trigger | Outdoor < Indoor | Outdoor > Indoor |
| Heat Flow Direction | Heat needs to be added | Heat needs to be removed |
| Effect of Solar Gains | Reduces heating demand | Increases cooling demand |
| Effect of Internal Gains | Reduces heating demand | Increases cooling demand |
| Humidity Consideration | Minimal impact | Significant impact (latent heat) |

### 1.2. Current Implementation Limitations

The current implementation in EMHASS has several limitations for dual-mode operation:

1. Calculates heating demand only
2. Uses a signed temperature difference that doesn't properly separate heating and cooling needs
3. Doesn't account for the opposing effect of solar and internal gains in heating vs. cooling modes

## 2. Dual Demand Calculation Function

We'll implement a new function `calculate_dual_thermal_demand` that calculates both heating and cooling demands simultaneously:

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
    Calculate both heating and cooling demands simultaneously for each timestep.
    
    This function separates heating and cooling demands based on the temperature
    difference between indoor and outdoor conditions. It also properly accounts
    for solar and internal gains having opposite effects on heating vs cooling.
    
    The latent_cooling_factor parameter represents additional cooling needed for
    dehumidification (typically 20-40% of sensible cooling load).
    
    :return: Dictionary containing component arrays including 'heating_demand_kwh'
             and 'cooling_demand_kwh' for each timestep
    """
    # Implementation details...
```

## 3. Temperature Difference Calculation

The key to proper separation of heating and cooling demands is to calculate two distinct temperature differences:

```python
# Convert outdoor temperatures to numpy array
outdoor_temps = (
    outdoor_temperature_forecast.values
    if isinstance(outdoor_temperature_forecast, pd.Series)
    else np.asarray(outdoor_temperature_forecast)
)

# Calculate separate temperature differences for heating and cooling
# For heating: we need indoor > outdoor (positive value means heating need)
heating_temp_diff = np.maximum(indoor_target_temperature - outdoor_temps, 0.0)

# For cooling: we need outdoor > indoor (positive value means cooling need)
cooling_temp_diff = np.maximum(outdoor_temps - indoor_target_temperature, 0.0)
```

This approach ensures that:
- When outdoor temperature is below indoor target, only heating_temp_diff is positive
- When outdoor temperature is above indoor target, only cooling_temp_diff is positive
- At the balance point (outdoor = indoor), both are zero

## 4. Transmission and Ventilation Loads

For both heating and cooling, the sensible thermal load comes from two main components:

```python
# Transmission losses/gains through the building envelope
heating_transmission_kw = u_value * envelope_area * heating_temp_diff / 1000.0
cooling_transmission_kw = u_value * envelope_area * cooling_temp_diff / 1000.0

# Ventilation losses/gains from air exchange
air_density = 1.2  # kg/m³
air_heat_capacity = 1.005  # kJ/(kg·K)
heating_ventilation_kw = (
    ventilation_rate * heated_volume * air_density * air_heat_capacity * heating_temp_diff / 3600.0
)
cooling_ventilation_kw = (
    ventilation_rate * heated_volume * air_density * air_heat_capacity * cooling_temp_diff / 3600.0
)

# Total sensible thermal loads
heating_load_kw = heating_transmission_kw + heating_ventilation_kw
cooling_load_kw = cooling_transmission_kw + cooling_ventilation_kw
```

## 5. Solar and Internal Gains

Solar and internal gains have opposite effects on heating and cooling demands:

```python
# Calculate solar gains if data is available
solar_gains_kw = np.zeros_like(outdoor_temps)
if solar_irradiance_forecast is not None and window_area is not None:
    # Process solar irradiance data
    solar_irradiance = (
        solar_irradiance_forecast.values
        if isinstance(solar_irradiance_forecast, pd.Series)
        else np.asarray(solar_irradiance_forecast)
    ).reshape(-1)
    
    # Calculate solar heat gain
    window_projection_factor = 0.3
    solar_gains_kw = window_area * shgc * solar_irradiance * window_projection_factor / 1000.0

# Calculate internal gains if data is available
internal_gains_kw = np.zeros_like(outdoor_temps)
if internal_gains_forecast is not None and internal_gains_factor > 0:
    # Process internal gains data
    internal_gains = (
        internal_gains_forecast.values
        if isinstance(internal_gains_forecast, pd.Series)
        else np.asarray(internal_gains_forecast)
    ).reshape(-1)
    
    # Calculate internal heat gains
    internal_gains_kw = internal_gains * internal_gains_factor / 1000.0

# Total gains
total_gains_kw = solar_gains_kw + internal_gains_kw

# Convert to kWh
hours = optimization_time_step / 60.0
heating_load_kwh = heating_load_kw * hours
cooling_load_kwh = cooling_load_kw * hours
solar_gains_kwh = solar_gains_kw * hours
internal_gains_kwh = internal_gains_kw * hours
total_gains_kwh = total_gains_kw * hours
```

## 6. Final Demand Calculations

The final demands are calculated differently for heating and cooling:

```python
# For heating: demand = load - gains (gains reduce heating need)
heating_demand_kwh = np.maximum(heating_load_kwh - total_gains_kwh, 0.0)

# For cooling: demand = load + gains (gains increase cooling need) + latent load
# Latent cooling accounts for dehumidification (typically 20-40% of sensible load)
sensible_cooling_kwh = np.maximum(cooling_load_kwh + total_gains_kwh, 0.0)
latent_cooling_kwh = sensible_cooling_kwh * latent_cooling_factor
cooling_demand_kwh = sensible_cooling_kwh + latent_cooling_kwh
```

## 7. Complete Function Implementation

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
    Calculate both heating and cooling demand components simultaneously for each timestep.
    
    :param u_value: Overall heat transfer coefficient in W/(m²·K)
    :param envelope_area: Building envelope area in m²
    :param ventilation_rate: Air changes per hour (ACH)
    :param heated_volume: Heated volume in m³
    :param indoor_target_temperature: Target indoor temperature in °C
    :param outdoor_temperature_forecast: Outdoor temperatures in °C
    :param optimization_time_step: Time step in minutes
    :param solar_irradiance_forecast: Solar irradiance in W/m² (optional)
    :param window_area: Window area in m² (optional)
    :param shgc: Solar Heat Gain Coefficient (optional, default: 0.6)
    :param internal_gains_forecast: Internal heat gains in W (optional)
    :param internal_gains_factor: Internal gains factor (optional, default: 0.0)
    :param latent_cooling_factor: Additional cooling for dehumidification as a
                                 fraction of sensible cooling (default: 0.3)
    :return: Dictionary with component arrays including heating_demand_kwh and
             cooling_demand_kwh
    """
    # Convert outdoor temperature to numpy array
    outdoor_temps = (
        outdoor_temperature_forecast.values
        if isinstance(outdoor_temperature_forecast, pd.Series)
        else np.asarray(outdoor_temperature_forecast)
    )
    
    # Calculate separate temperature differences for heating and cooling
    heating_temp_diff = np.maximum(indoor_target_temperature - outdoor_temps, 0.0)
    cooling_temp_diff = np.maximum(outdoor_temps - indoor_target_temperature, 0.0)
    
    # Transmission losses/gains
    heating_transmission_kw = u_value * envelope_area * heating_temp_diff / 1000.0
    cooling_transmission_kw = u_value * envelope_area * cooling_temp_diff / 1000.0
    
    # Ventilation losses/gains
    air_density = 1.2  # kg/m³
    air_heat_capacity = 1.005  # kJ/(kg·K)
    heating_ventilation_kw = (
        ventilation_rate * heated_volume * air_density * air_heat_capacity * 
        heating_temp_diff / 3600.0
    )
    cooling_ventilation_kw = (
        ventilation_rate * heated_volume * air_density * air_heat_capacity * 
        cooling_temp_diff / 3600.0
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
        
        if len(solar_irradiance) != len(outdoor_temps):
            raise ValueError(
                f"solar_irradiance_forecast length ({len(solar_irradiance)}) must match "
                f"outdoor_temperature_forecast length ({len(outdoor_temps)})"
            )
        
        window_projection_factor = 0.3
        solar_gains_kw = window_area * shgc * solar_irradiance * window_projection_factor / 1000.0
    
    # Internal gains calculation
    internal_gains_kw = np.zeros_like(outdoor_temps)
    if internal_gains_forecast is not None and internal_gains_factor > 0:
        if internal_gains_factor < 0 or internal_gains_factor > 1:
            raise ValueError(
                f"internal_gains_factor must be between 0 and 1, got {internal_gains_factor}"
            )
        
        internal_gains = (
            internal_gains_forecast.values
            if isinstance(internal_gains_forecast, pd.Series)
            else np.asarray(internal_gains_forecast)
        ).reshape(-1)
        
        if len(internal_gains) != len(outdoor_temps):
            raise ValueError(
                f"internal_gains_forecast length ({len(internal_gains)}) must match "
                f"outdoor_temperature_forecast length ({len(outdoor_temps)})"
            )
        
        internal_gains_kw = internal_gains * internal_gains_factor / 1000.0
    
    # Total gains
    total_gains_kw = solar_gains_kw + internal_gains_kw
    
    # Convert to kWh
    hours = optimization_time_step / 60.0
    heating_load_kwh = heating_load_kw * hours
    cooling_load_kwh = cooling_load_kw * hours
    solar_gains_kwh = solar_gains_kw * hours
    internal_gains_kwh = internal_gains_kw * hours
    total_gains_kwh = total_gains_kw * hours
    
    # Final demand calculations
    heating_demand_kwh = np.maximum(heating_load_kwh - total_gains_kwh, 0.0)
    
    sensible_cooling_kwh = np.maximum(cooling_load_kwh + total_gains_kwh, 0.0)
    latent_cooling_kwh = sensible_cooling_kwh * latent_cooling_factor
    cooling_demand_kwh = sensible_cooling_kwh + latent_cooling_kwh
    
    return {
        "heating_load_kwh": heating_load_kwh,
        "cooling_load_kwh": cooling_load_kwh,
        "solar_gains_kwh": solar_gains_kwh,
        "internal_gains_kwh": internal_gains_kwh,
        "heating_demand_kwh": heating_demand_kwh,
        "sensible_cooling_kwh": sensible_cooling_kwh,
        "latent_cooling_kwh": latent_cooling_kwh,
        "cooling_demand_kwh": cooling_demand_kwh,
    }
```

## 8. Integration with Thermal Battery Constraints

To use this new demand calculation function in the thermal battery constraints:

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    # ... (existing setup code)
    
    # Calculate dual thermal demands
    thermal_demands = utils.calculate_dual_thermal_demand(
        u_value=hc["u_value"],
        envelope_area=hc["envelope_area"],
        ventilation_rate=hc["ventilation_rate"],
        heated_volume=hc["heated_volume"],
        indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
        optimization_time_step=int(self.freq.total_seconds() / 60),
        solar_irradiance_forecast=solar_irradiance,
        window_area=hc.get("window_area"),
        shgc=hc.get("shgc", 0.6),
        internal_gains_forecast=p_load if hc.get("internal_gains_factor", 0.0) > 0 else None,
        internal_gains_factor=hc.get("internal_gains_factor", 0.0),
        latent_cooling_factor=hc.get("latent_cooling_factor", 0.3),
    )
    
    # Store demand values in parameters
    params["heating_demand"].value = np.array(thermal_demands["heating_demand_kwh"][:required_len])
    params["cooling_demand"].value = np.array(thermal_demands["cooling_demand_kwh"][:required_len])
    params["solar_gains"].value = np.array(thermal_demands["solar_gains_kwh"][:required_len])
    
    # Use in temperature dynamics
    heating_demand = params["heating_demand"].value
    cooling_demand = params["cooling_demand"].value
    solar_gains = params["solar_gains"].value
    
    # ... (rest of constraint generation)
```

## 9. Backward Compatibility

To maintain backward compatibility with existing code:

```python
# Wrapper function for backward compatibility
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
    Backward compatible wrapper around calculate_dual_thermal_demand.
    Calculates heating or cooling demand components based on mode.
    
    :param mode: Operating mode, either "heat" (default) or "cool"
    """
    # Calculate both heating and cooling demands
    all_demands = calculate_dual_thermal_demand(
        u_value=u_value,
        envelope_area=envelope_area,
        ventilation_rate=ventilation_rate,
        heated_volume=heated_volume,
        indoor_target_temperature=indoor_target_temperature,
        outdoor_temperature_forecast=outdoor_temperature_forecast,
        optimization_time_step=optimization_time_step,
        solar_irradiance_forecast=solar_irradiance_forecast,
        window_area=window_area,
        shgc=shgc,
        internal_gains_forecast=internal_gains_forecast,
        internal_gains_factor=internal_gains_factor,
    )
    
    # Return heating or cooling components based on mode
    if mode == "heat":
        return {
            "heat_loss_kwh": all_demands["heating_load_kwh"],
            "solar_gains_kwh": all_demands["solar_gains_kwh"],
            "internal_gains_kwh": all_demands["internal_gains_kwh"],
            "heating_demand_kwh": all_demands["heating_demand_kwh"],
        }
    elif mode == "cool":
        return {
            "heat_loss_kwh": all_demands["cooling_load_kwh"],
            "solar_gains_kwh": all_demands["solar_gains_kwh"],
            "internal_gains_kwh": all_demands["internal_gains_kwh"],
            "heating_demand_kwh": all_demands["cooling_demand_kwh"],  # Same key for backward compatibility
        }
    else:
        raise ValueError(f"Mode must be 'heat' or 'cool', got '{mode}'")
```

## 10. Energy Balance Equation

The energy balance equation in the temperature dynamics must be updated to account for both heating and cooling demands:

```python
# Temperature dynamics with both heating and cooling demands
constraints.append(
    pred_temp[1:] == (
        pred_temp[:-1] + 
        # Heating power adds heat to the system
        (p_heat[:-1] * heat_cops[:-1] * conversion) - 
        # Cooling power removes heat from the system 
        (p_cool[:-1] * cool_cops[:-1] * conversion) - 
        # Thermal losses to the environment
        (thermal_losses[:-1] * conversion) - 
        # Heating demand (negative, represents heat the system provides)
        (heating_demand[:-1] * conversion) +
        # Cooling demand (positive, represents heat that enters the system)
        (cooling_demand[:-1] * conversion) +
        # Solar gains add heat
        (solar_gains[:-1] * conversion)
    )
)
```

## 11. Additional Configuration Options

New configuration options for the dual demand calculation:

```json
"thermal_battery": {
  // Existing parameters...
  
  // Cooling specific parameters
  "latent_cooling_factor": 0.3,  // Additional cooling for dehumidification (default: 0.3 = 30%)
  "cooling_setback": 2.0,        // Increased cooling setpoint during unoccupied periods (°C)
  
  // Seasonal parameters
  "winter_indoor_temperature": 21.0,  // Target temperature for heating season (°C)
  "summer_indoor_temperature": 24.0,  // Target temperature for cooling season (°C)
}
```

## 12. Performance Considerations

The dual demand calculation increases computational complexity slightly, but this can be mitigated by:

1. **Vectorization**: All calculations are vectorized for efficiency
2. **Parameter Caching**: Store calculated demands in parameters for reuse
3. **Limiting Recalculation**: Only recalculate when inputs change
4. **Efficient Arrays**: Use numpy arrays for all calculations

## 13. Testing Recommendations

Tests should verify:

1. **Temperature Direction**: Correct demand calculation based on indoor/outdoor temperature differences
2. **Solar Gain Effects**: Solar gains reduce heating demand and increase cooling demand
3. **Internal Gain Effects**: Internal gains reduce heating demand and increase cooling demand
4. **Latent Cooling**: Proper calculation of additional cooling for dehumidification
5. **Edge Cases**: Correct behavior at balance point (outdoor = indoor) temperatures
6. **Seasonal Behavior**: Appropriate demands calculated in different seasonal scenarios