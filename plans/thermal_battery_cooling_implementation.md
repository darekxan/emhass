# GSHP Active Cooling Support for thermal_battery Implementation Plan

## Overview

This plan outlines the changes needed to add Ground Source Heat Pump (GSHP) active cooling support to EMHASS's thermal_battery component. Currently, the thermal_battery model only supports heating mode, while the simpler thermal_config model already supports both heating and cooling through the "sense" parameter.

## Current Implementation Analysis

### Thermal Models Comparison

| Feature | thermal_config | thermal_battery |
|---------|---------------|-----------------|
| Model Type | Simple linear model | Complex thermal mass storage model |
| Heating/Cooling | Both via "sense" parameter | Heating only |
| Temperature Control | Direct via desired temp | Via min/max temps + optimization |
| COP Modeling | None | Complex model based on outdoor temp |
| Demand Calculation | None | Physics-based or HDD-based |

### Key Code Locations

1. **Main thermal_battery implementation**: `src/emhass/optimization.py` in `_add_thermal_battery_constraints()`
2. **COP calculation**: `src/emhass/utils.py` in `calculate_cop_heatpump()`
3. **Physics-based demand calculation**: `src/emhass/utils.py` in `calculate_heating_demand_physics_components()`
4. **Documentation**: `docs/thermal_battery.md`

## Changes Required

### 1. Add "sense" Parameter to thermal_battery

- Update thermal_battery configuration to accept a "sense" parameter ("heat" or "cool")
- Default to "heat" for backward compatibility
- Add validation for the parameter value

### 2. Modify COP Calculation for Cooling Mode

The current COP calculation in `utils.calculate_cop_heatpump()` is designed for heating mode. For cooling mode:

- Add a mode parameter to the function
- For cooling, implement a different COP formula:
  - Consider that cooling COPs are typically higher than heating COPs at the same temperatures
  - Adjust the Carnot efficiency calculation for cooling operation
- Update function documentation to clarify the two modes

### 3. Update Temperature Dynamics Calculation

The thermal_battery model currently assumes a heating operation where:
- Heat pump provides heat to the thermal mass
- Higher COP is better

For cooling operation:
- Need to invert the energy flow direction
- Use a sense_coeff multiplier (-1 for cooling, 1 for heating)
- Ensure the optimizer correctly minimizes electrical energy usage

### 4. Implement Cooling Demand Calculation

Update the physics-based model to calculate cooling demand:

- Modify `calculate_heating_demand_physics_components()` function to handle cooling
- For cooling, solar gains increase cooling load (opposite of heating)
- Internal gains contribute to cooling load rather than reducing it
- Consider both sensible cooling and latent cooling (dehumidification) if applicable

### 5. Handle Temperature Constraints for Cooling Mode

For cooling mode:
- Ensure min/max temperature constraints are properly applied
- The constraint direction logic needs careful handling
- Typically in cooling mode:
  - Maximum temperature is the trigger point to start cooling
  - Minimum temperature is the comfort/energy saving limit

### 6. Update Sensor Publishing

- Modify sensor naming or data to indicate cooling operation
- Ensure energy metrics properly account for cooling operation
- Consider adding mode (heating/cooling) to published data

### 7. Update Documentation

- Update `thermal_battery.md` to document the new cooling capabilities
- Add examples for cooling mode configuration
- Document any new parameters or modified behavior
- Update examples and recommendations for cooling applications

## Implementation Approach

1. Start by adding the "sense" parameter and related logic changes
2. Update COP calculation to support cooling mode
3. Modify temperature dynamics and constraints handling
4. Implement cooling demand calculation
5. Update sensor publishing logic
6. Update documentation and examples
7. Add test cases

## Testing Strategy

- Create test cases for cooling mode configuration
- Test with different COP values and outdoor temperature scenarios
- Verify correct optimization behavior in cooling mode
- Test transitions between heating and cooling modes
- Compare with expected values calculated manually
- Ensure backward compatibility with existing heating-only configurations