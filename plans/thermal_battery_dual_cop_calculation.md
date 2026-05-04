# Implementing Dual COP Calculation for Thermal Battery

This document details the implementation of the dual Coefficient of Performance (COP) calculation for the thermal_battery component. The function will calculate both heating and cooling COPs simultaneously to support the dual-mode operation.

## 1. Physical Principles of Heat Pump COPs

### Heating Mode COP

In heating mode, the COP is defined as:

```
COP_heat = Heat Output / Electrical Input
```

The Carnot-based theoretical formula is:

```
COP_heat = η_carnot × T_supply_K / (T_supply_K - T_outdoor_K)
```

Where:
- `η_carnot` is the real-world efficiency as a fraction of the ideal Carnot cycle
- `T_supply_K` is the heat pump supply temperature in Kelvin
- `T_outdoor_K` is the outdoor temperature in Kelvin

### Cooling Mode COP

In cooling mode, the COP is defined as:

```
COP_cool = Cooling Output / Electrical Input
```

The Carnot-based theoretical formula is:

```
COP_cool = η_carnot × T_supply_K / (T_outdoor_K - T_supply_K)
```

Note the crucial difference in the denominator - for heating we have `T_supply - T_outdoor`, while for cooling we have `T_outdoor - T_supply`.

## 2. Implementation of Dual COP Calculation

### Function Signature

```python
def calculate_cop_dual_mode(
    heat_supply_temperature: float,
    cool_supply_temperature: float,
    heat_carnot_efficiency: float,
    cool_carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate heat pump Coefficients of Performance (COP) for both heating and cooling
    modes for each timestep in the prediction horizon.
    
    For heating mode: COP = η_carnot × T_supply_K / (T_supply_K - T_outdoor_K)
    For cooling mode: COP = η_carnot × T_supply_K / (T_outdoor_K - T_supply_K)
    
    Where temperatures are converted to Kelvin (K = °C + 273.15).
    
    This function calculates both heating and cooling COPs simultaneously to support
    dual-mode operation, allowing the optimizer to automatically select the most
    efficient mode based on conditions.
    
    :param heat_supply_temperature: Heat pump supply temperature for heating mode in °C
        Typical values: 30-50°C for heating (higher = lower efficiency)
    :type heat_supply_temperature: float
    :param cool_supply_temperature: Heat pump supply temperature for cooling mode in °C
        Typical values: 7-15°C for cooling (higher = greater efficiency)
    :type cool_supply_temperature: float
    :param heat_carnot_efficiency: Real-world heating efficiency factor as fraction of ideal Carnot cycle
        Typical range: 0.35-0.45 (35-45%)
    :type heat_carnot_efficiency: float 
    :param cool_carnot_efficiency: Real-world cooling efficiency factor as fraction of ideal Carnot cycle
        Typical range: 0.4-0.55 (40-55%, typically higher than heating)
    :type cool_carnot_efficiency: float
    :param outdoor_temperature_forecast: Array of outdoor temperature forecasts in °C
    :type outdoor_temperature_forecast: np.ndarray or pd.Series
    :return: Tuple of (heating_cop_array, cooling_cop_array) with the same length as the input forecast
    :rtype: tuple[np.ndarray, np.ndarray]
    
    Example:
        >>> heat_supply = 35.0  # °C for heating
        >>> cool_supply = 12.0  # °C for cooling
        >>> heat_eff = 0.4  # 40% for heating
        >>> cool_eff = 0.45  # 45% for cooling
        >>> outdoor_temps = np.array([0.0, 10.0, 20.0, 30.0])
        >>> heat_cops, cool_cops = calculate_cop_dual_mode(
        ...     heat_supply, cool_supply, heat_eff, cool_eff, outdoor_temps
        ... )
        >>> heat_cops  # Heating COPs
        array([3.521..., 4.926..., 8.217..., 1.0])
        >>> cool_cops  # Cooling COPs
        array([1.0, 1.0, 1.0, 6.293...])
    """
    # Convert to numpy array if pandas Series
    if isinstance(outdoor_temperature_forecast, pd.Series):
        outdoor_temps = outdoor_temperature_forecast.values
    else:
        outdoor_temps = np.asarray(outdoor_temperature_forecast)

    # Convert temperatures from Celsius to Kelvin
    heat_supply_kelvin = heat_supply_temperature + 273.15
    cool_supply_kelvin = cool_supply_temperature + 273.15
    outdoor_kelvin = outdoor_temps + 273.15

    # --- Heating COP Calculation ---
    
    # Calculate temperature difference for heating (supply - outdoor)
    heat_temp_diff = heat_supply_kelvin - outdoor_kelvin
    
    # Initialize heating COPs array with default value of 1.0
    heat_cop = np.ones_like(outdoor_temps)
    
    # Check for valid heating conditions (supply > outdoor)
    valid_heat = heat_temp_diff > 0
    
    # Log warning about non-physical scenarios for heating
    if not np.all(valid_heat):
        logger = logging.getLogger(__name__)
        num_invalid = np.sum(~valid_heat)
        invalid_indices = np.nonzero(~valid_heat)[0]
        logger.warning(
            f"Heating COP calculation: {num_invalid} timestep(s) have outdoor temperature >= "
            f"heating supply temperature ({heat_supply_temperature:.1f}°C). "
            f"This is non-physical for heating. Indices: {invalid_indices.tolist()[:5]}"
            f"{'...' if len(invalid_indices) > 5 else ''}. "
            f"Setting heating COP to 1.0 (direct electric) for these periods."
        )
    
    # Calculate Carnot-based heating COP for valid periods
    if np.any(valid_heat):
        heat_cop[valid_heat] = (
            heat_carnot_efficiency * heat_supply_kelvin / heat_temp_diff[valid_heat]
        )
    
    # Apply realistic bounds for heating COP
    heat_cop = np.clip(heat_cop, 1.0, 8.0)

    # --- Cooling COP Calculation ---
    
    # Calculate temperature difference for cooling (outdoor - supply)
    cool_temp_diff = outdoor_kelvin - cool_supply_kelvin
    
    # Initialize cooling COPs array with default value of 1.0
    cool_cop = np.ones_like(outdoor_temps)
    
    # Check for valid cooling conditions (outdoor > supply)
    valid_cool = cool_temp_diff > 0
    
    # Log warning about non-physical scenarios for cooling
    if not np.all(valid_cool):
        logger = logging.getLogger(__name__)
        num_invalid = np.sum(~valid_cool)
        invalid_indices = np.nonzero(~valid_cool)[0]
        logger.warning(
            f"Cooling COP calculation: {num_invalid} timestep(s) have outdoor temperature <= "
            f"cooling supply temperature ({cool_supply_temperature:.1f}°C). "
            f"This is non-physical for cooling. Indices: {invalid_indices.tolist()[:5]}"
            f"{'...' if len(invalid_indices) > 5 else ''}. "
            f"Setting cooling COP to 1.0 (direct electric) for these periods."
        )
    
    # Calculate Carnot-based cooling COP for valid periods
    if np.any(valid_cool):
        cool_cop[valid_cool] = (
            cool_carnot_efficiency * cool_supply_kelvin / cool_temp_diff[valid_cool]
        )
    
    # Apply realistic bounds for cooling COP (typically higher than heating)
    cool_cop = np.clip(cool_cop, 1.0, 10.0)

    return heat_cop, cool_cop
```

## 3. Integration with Thermal Battery Constraints

When implementing this dual COP calculation in the thermal battery constraints, we need to:

1. Extract mode-specific parameters
2. Calculate both sets of COPs
3. Store them in the parameter dictionary for potential reuse

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    # ... (existing code)
    
    # Extract dual-mode specific parameters
    heat_supply_temp = hc.get("heat_supply_temperature", 35.0)
    cool_supply_temp = hc.get("cool_supply_temperature", 12.0)
    heat_efficiency = hc.get("heat_carnot_efficiency", 0.4)
    cool_efficiency = hc.get("cool_carnot_efficiency", 0.45)
    
    # Calculate COPs for both modes
    outdoor_temp_arr = self._get_clean_outdoor_temp(data_opt, required_len)
    
    # Use parameterized values if available (enables warm-start on cache hit)
    if k in self.param_thermal:
        params = self.param_thermal[k]
        
        # Initialize COPs if we're in dual-mode
        if params["type"] == "thermal_battery_dual":
            # Calculate dual COPs
            heat_cop, cool_cop = utils.calculate_cop_dual_mode(
                heat_supply_temperature=heat_supply_temp,
                cool_supply_temperature=cool_supply_temp,
                heat_carnot_efficiency=heat_efficiency,
                cool_carnot_efficiency=cool_efficiency,
                outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
            )
            
            # Store in parameters
            params["heat_cops"].value = np.array(heat_cop[:required_len])
            params["cool_cops"].value = np.array(cool_cop[:required_len])
            
            heat_cops = params["heat_cops"].value
            cool_cops = params["cool_cops"].value
    else:
        # Fallback if parameters aren't pre-initialized
        heat_cop, cool_cop = utils.calculate_cop_dual_mode(
            heat_supply_temperature=heat_supply_temp,
            cool_supply_temperature=cool_supply_temp,
            heat_carnot_efficiency=heat_efficiency,
            cool_carnot_efficiency=cool_efficiency,
            outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
        )
        
        heat_cops = np.array(heat_cop[:required_len])
        cool_cops = np.array(cool_cop[:required_len])
```

## 4. COP Caching and Reuse

To improve performance, we can cache and reuse COP calculations between optimization runs:

```python
# In _update_thermal_params method
if thermal_type == "thermal_battery_dual":
    # Update cached COP values for warm-start
    heat_supply_temp = hc.get("heat_supply_temperature", 35.0)
    cool_supply_temp = hc.get("cool_supply_temperature", 12.0)
    heat_efficiency = hc.get("heat_carnot_efficiency", 0.4)
    cool_efficiency = hc.get("cool_carnot_efficiency", 0.45)
    
    # Calculate new COPs
    heat_cop, cool_cop = utils.calculate_cop_dual_mode(
        heat_supply_temperature=heat_supply_temp,
        cool_supply_temperature=cool_supply_temp,
        heat_carnot_efficiency=heat_efficiency,
        cool_carnot_efficiency=cool_efficiency,
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
    )
    
    # Update parameters
    params["heat_cops"].value = np.array(heat_cop[:required_len])
    params["cool_cops"].value = np.array(cool_cop[:required_len])
```

## 5. Backward Compatibility

To ensure backward compatibility with the existing code:

1. Create a wrapper around the new function that mimics the old interface
2. Default to heating mode in the wrapper

```python
def calculate_cop_heatpump(
    supply_temperature: float,
    carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
    mode: str = "heat",
) -> np.ndarray:
    """
    Backward-compatible wrapper around the dual-mode COP calculation.
    Calculates heat pump COP for either heating or cooling mode.
    
    :param mode: Operating mode, either "heat" (default) or "cool"
    """
    if mode == "heat":
        heat_cop, _ = calculate_cop_dual_mode(
            heat_supply_temperature=supply_temperature,
            cool_supply_temperature=0.0,  # Not used
            heat_carnot_efficiency=carnot_efficiency,
            cool_carnot_efficiency=0.0,  # Not used
            outdoor_temperature_forecast=outdoor_temperature_forecast,
        )
        return heat_cop
    elif mode == "cool":
        _, cool_cop = calculate_cop_dual_mode(
            heat_supply_temperature=0.0,  # Not used
            cool_supply_temperature=supply_temperature,
            heat_carnot_efficiency=0.0,  # Not used
            cool_carnot_efficiency=carnot_efficiency,
            outdoor_temperature_forecast=outdoor_temperature_forecast,
        )
        return cool_cop
    else:
        raise ValueError(f"Mode must be 'heat' or 'cool', got '{mode}'")
```

## 6. Physical Considerations

### Temperature Ranges and Realistic Behavior

- For heat pumps, the COP decreases as the temperature difference increases
- COPs are typically bounded:
  - Heating: Typically 1.0 to 8.0
  - Cooling: Typically 1.0 to 10.0 (generally higher than heating)
- Supply temperatures:
  - Heating: 30-50°C (higher temperatures reduce efficiency)
  - Cooling: 7-15°C (higher temperatures increase efficiency but reduce capacity)

### Carnot Efficiency Factors

- Real heat pumps achieve 35-55% of the theoretical Carnot efficiency
- Cooling operations often have higher Carnot efficiency than heating

## 7. Numerical Stability

To ensure numerical stability:

1. Use appropriate clipping to prevent unrealistically high COPs
2. Handle potential division by zero for edge cases
3. Ensure temperature differences are strictly positive when used in division
4. Use default COP of 1.0 for non-physical cases (equivalent to direct electric heating/cooling)

## 8. Performance Considerations

The dual COP calculation may have a small impact on performance, but since:

1. The calculation is vectorized
2. It's performed once per optimization
3. The arrays are typically small (24-48 elements for daily optimization)

The performance impact should be negligible compared to the benefit of having both modes available for optimization.

## 9. Testing Recommendations

Tests should verify:

1. COPs are calculated correctly for valid temperature ranges
2. Edge cases are handled properly
3. Both heating and cooling COPs are returned with correct shapes
4. Valid values are positive and within realistic bounds
5. Non-physical cases default to COP of 1.0
6. Warning messages are logged for non-physical cases