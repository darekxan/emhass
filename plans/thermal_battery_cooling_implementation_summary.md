# GSHP Active Cooling Support for thermal_battery - Implementation Summary

## Introduction

This document provides a comprehensive summary of the planning and design work for implementing Ground Source Heat Pump (GSHP) active cooling support in the EMHASS thermal_battery component. Currently, the thermal_battery component only supports heating mode, while the simpler thermal_config component supports both heating and cooling. This implementation will extend the thermal_battery component to support cooling operation, enabling more efficient energy management during hot weather.

## Project Overview

### Motivation

Adding cooling support to the thermal_battery component will enable:

1. Optimization of GSHP systems that can operate in both heating and cooling modes
2. Better energy management during summer months
3. Increased solar PV self-consumption by using excess solar generation for cooling
4. Cost savings by running cooling during periods of lower electricity prices
5. Improved comfort through optimized temperature control

### Key Differences Between Heating and Cooling Modes

| Aspect | Heating Mode | Cooling Mode |
|--------|-------------|-------------|
| Energy Flow | Heat added to building | Heat removed from building |
| Temperature Direction | Increases when running | Decreases when running |
| Outdoor Temperature Impact | Demand increases when outdoor is colder | Demand increases when outdoor is hotter |
| Solar Gains | Reduce heating demand | Increase cooling demand |
| Internal Gains | Reduce heating demand | Increase cooling demand |
| COP Calculation | Based on T_supply / (T_supply - T_outdoor) | Based on T_supply / (T_outdoor - T_supply) |
| Supply Temperature | Typically 30-50°C | Typically 7-15°C |

## Implementation Plan

The implementation requires changes to several components in the EMHASS codebase:

### 1. Core Functions in `utils.py`

- Modify `calculate_cop_heatpump()` to support cooling mode
- Update `calculate_heating_demand_physics_components()` to handle cooling demand calculation
- Adjust thermal loss calculations for cooling operation

### 2. Optimization Module in `optimization.py`

- Add "sense" parameter to thermal_battery configuration
- Update thermal battery constraint generation for cooling mode
- Implement sense coefficient to flip calculations based on mode
- Adjust temperature dynamics equations and objectives

### 3. Sensor Publishing in `web_server.py`

- Update sensor naming and attributes to indicate cooling operation
- Add mode-specific icons and friendly names
- Ensure backward compatibility for existing heating configurations

### 4. Documentation in `thermal_battery.md`

- Document the new cooling capabilities
- Provide example configurations
- Explain parameter adjustments for cooling mode
- Add troubleshooting guidance

### 5. Test Suite

- Add unit tests for COP calculation and demand calculation
- Implement integration tests for the full optimization process
- Create realistic scenario tests for cooling operation

## Technical Challenges and Solutions

### 1. COP Calculation for Cooling

**Challenge**: The COP formula needs to be inverted for cooling mode, and boundary conditions are different.

**Solution**: Add a mode parameter to the function and implement separate calculation paths for heating and cooling, with appropriate boundary checks and limits.

```python
def calculate_cop_heatpump(
    supply_temperature: float,
    carnot_efficiency: float,
    outdoor_temperature_forecast: np.ndarray | pd.Series,
    mode: str = "heat",
) -> np.ndarray:
    # Implementation with separate paths for heating and cooling
    if mode == "heat":
        temperature_diff = supply_temperature_kelvin - outdoor_temperature_kelvin
    else:  # cooling mode
        temperature_diff = outdoor_temperature_kelvin - supply_temperature_kelvin
    
    # Rest of implementation...
```

### 2. Handling Solar Gains in Cooling Mode

**Challenge**: In heating mode, solar gains reduce heating demand, but in cooling mode, they increase cooling demand.

**Solution**: Flip the sign of solar gains in the thermal demand calculation based on mode:

```python
if mode == "heat":
    # For heating, gains reduce demand
    thermal_demand_kwh = heat_loss_kwh - solar_gains_kwh - internal_gains_kwh
else:  # cooling mode
    # For cooling, gains increase demand
    thermal_demand_kwh = heat_loss_kwh + solar_gains_kwh + internal_gains_kwh
```

### 3. Temperature Dynamics in Optimization

**Challenge**: The temperature evolution equations need to account for the direction of energy flow in cooling mode.

**Solution**: Implement a sense coefficient (1 for heating, -1 for cooling) to adjust the temperature dynamics:

```python
sense_coeff = 1 if sense == "heat" else -1

constraints.append(
    pred_temp[1:] == (
        pred_temp[:-1] 
        + (sense_coeff * p_deferrable[:-1] * heatpump_cops[:-1] * 1.0 * conversion) 
        - (thermal_losses[:-1] * conversion)
        - (sense_coeff * heating_demand[:-1] * conversion)
        + (solar_gains[:-1] * conversion)
    )
)
```

### 4. Backward Compatibility

**Challenge**: Ensuring existing heating configurations continue to work unchanged.

**Solution**: Make cooling mode opt-in by defaulting to heating when no sense parameter is specified:

```python
sense = hc.get("sense", "heat")
```

## Recommendations for Implementation

### Phased Approach

1. **Phase 1**: Implement core function changes in `utils.py`
   - COP calculation for cooling
   - Demand calculation with cooling support

2. **Phase 2**: Update the thermal battery constraints in `optimization.py`
   - Add sense parameter
   - Implement temperature dynamics with sense coefficient

3. **Phase 3**: Update sensor publishing in `web_server.py`
   - Update sensor attributes
   - Add mode-specific naming and icons

4. **Phase 4**: Update documentation and add tests
   - Document the new cooling capabilities
   - Implement comprehensive test suite

### Testing Strategy

- Test each component individually with unit tests
- Test the complete optimization flow with integration tests
- Test realistic scenarios with seasonal data
- Verify backward compatibility with existing configurations
- Test edge cases (extreme temperatures, transition periods)

## Conclusion

The implementation of GSHP active cooling support for the thermal_battery component will significantly enhance EMHASS's capabilities for year-round energy optimization. The changes required are substantial but well-defined, touching several key areas of the codebase. With the detailed technical specifications and code examples provided in this project, developers can confidently implement this feature following the phased approach outlined above.

## Next Steps

1. Review the implementation plan with the EMHASS development team
2. Prioritize implementation phases based on project roadmap
3. Begin implementation with the core function changes in `utils.py`
4. Follow with changes to the optimization constraints
5. Complete with sensor publishing updates and documentation
6. Deploy comprehensive test suite to ensure reliability

By following this plan, EMHASS will gain valuable cooling optimization capabilities, enabling users to manage their home energy systems more effectively throughout the year.