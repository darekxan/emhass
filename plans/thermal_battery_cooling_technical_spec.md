# Technical Specification: GSHP Active Cooling Support for thermal_battery

## 1. Overview

This document provides detailed technical specifications for adding Ground Source Heat Pump (GSHP) active cooling support to the thermal_battery component in EMHASS. The implementation will allow users to model and optimize cooling operation with their ground source heat pumps using the existing thermal mass storage model.

## 2. Current Implementation Analysis

The thermal_battery component currently only supports heating mode, while the simpler thermal_config component supports both heating and cooling through a "sense" parameter. The current implementation has several key limitations for cooling:

1. No "sense" parameter in thermal_battery configuration
2. COP calculation only works for heating mode
3. Demand calculation assumes heating only (where indoor > outdoor temp)
4. Temperature dynamics don't consider cooling operation

## 3. Implementation Changes

### 3.1 File: `src/emhass/utils.py`

#### 3.1.1 Modify `calculate_cop_heatpump()`

```python
def calculate_cop_heatpump(
    supply_temperature: float,
    carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
    mode: str = "heat",
) -> np.ndarray:
    """
    Calculate heat pump Coefficient of Performance (COP) for each timestep in the prediction horizon.
    
    Supports both heating and cooling modes:
    - Heating: COP = η_carnot × T_supply_K / |T_supply_K - T_outdoor_K|
    - Cooling: COP = η_carnot × T_supply_K / |T_supply_K - T_outdoor_K|
    
    Where temperatures are converted to Kelvin (K = °C + 273.15).
    
    :param supply_temperature: The heat pump supply temperature in degrees Celsius
    :param carnot_efficiency: Real-world efficiency factor as fraction of ideal Carnot cycle
    :param outdoor_temperature_forecast: Array of outdoor temperature forecasts in degrees Celsius
    :param mode: Operating mode, either "heat" (default) or "cool"
    :return: Array of COP values for each timestep
    """
    # Implementation with mode handling...
```

Changes:
- Add `mode` parameter with default "heat" for backward compatibility
- Update documentation to describe both modes
- Add cooling-specific COP calculation
- Adjust warnings and boundary conditions for cooling mode
- Modify temperature difference calculations based on mode

#### 3.1.2 Modify `calculate_heating_demand_physics_components()`

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
    
    :param mode: Operating mode, either "heat" (default) or "cool"
    """
    # Implementation with mode handling...
```

Changes:
- Add `mode` parameter with default "heat" for backward compatibility
- Update documentation to describe both modes
- Modify temperature difference calculation logic for cooling
- Invert the effect of solar and internal gains for cooling mode

### 3.2 File: `src/emhass/optimization.py`

#### 3.2.1 Update `_add_thermal_battery_constraints()`

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    """
    Handle constraints for thermal battery loads (Vectorized, Legacy Match).
    Supports both heating and cooling modes via the 'sense' parameter.
    """
    # Extract mode from configuration
    sense = hc.get("sense", "heat")
    # Only valid values are "heat" or "cool"
    if sense not in ["heat", "cool"]:
        raise ValueError(f"Load {k}: thermal_battery sense must be 'heat' or 'cool', got '{sense}'")
    
    # Set sense coefficient for calculations
    sense_coeff = 1 if sense == "heat" else -1
    
    # Calculate COP with mode
    cops = utils.calculate_cop_heatpump(
        supply_temperature=supply_temperature,
        carnot_efficiency=hc.get("carnot_efficiency", 0.4),
        outdoor_temperature_forecast=outdoor_temp_arr.tolist(),
        mode=sense,
    )
```

Changes:
- Add "sense" parameter support to thermal_battery
- Introduce sense coefficient for flipping calculations
- Update COP calculation to pass mode
- Adjust thermal dynamics based on sense
- Modify heating/cooling demand calculation to respect mode
- Update temperature constraints handling for both modes

### 3.3 Documentation Updates

#### 3.3.1 File: `docs/thermal_battery.md`

Update the documentation to explain:
- New "sense" parameter and its usage
- How cooling mode works
- Example configurations for cooling
- Best practices for cooling optimization
- Differences in COP calculations between modes

## 4. Technical Considerations

### 4.1 Cooling Mode Physics

For cooling mode, several key physics principles need to be implemented:

1. **Reversed Energy Flow**: In cooling, energy flows from indoors to outdoors
2. **Temperature Difference**: Cooling demand increases when outdoor > indoor
3. **Solar & Internal Gains**: Increase cooling demand, unlike in heating
4. **COP Calculation**: Different formula based on cooling mode

### 4.2 Backward Compatibility

The implementation must maintain backward compatibility:
- Default to "heat" mode when "sense" is not specified
- Maintain the same API for existing functions
- Ensure existing heating configurations continue to work unchanged

### 4.3 Optimization Logic

The optimizer needs to handle cooling mode correctly:
- Flip objective function sign where appropriate
- Respect min/max temperature constraints
- Calculate cooling demand correctly
- Model COP for electric energy consumption

## 5. Testing Requirements

To ensure proper operation, testing should cover:

1. COP calculation in cooling mode
2. Temperature dynamics with cooling operation
3. Cooling demand calculation
4. Constraint satisfaction in optimization
5. Backward compatibility with existing heating configurations

## 6. User Experience

The implementation should be intuitive for users:

1. Simple configuration parameter ("sense": "cool")
2. Clear documentation with examples
3. Sensible defaults for backward compatibility
4. Proper validation and error messages for misconfiguration