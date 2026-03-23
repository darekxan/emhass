# Dual-Mode Thermal Battery Documentation

This document outlines the documentation updates needed for the thermal_battery.md file to include the new dual-mode (heating and cooling) capabilities.

## 1. Introduction to Dual-Mode Section

Add this section immediately after the existing introduction:

```markdown
## Dual-Mode Operation (Heating and Cooling)

EMHASS now supports dual-mode operation for thermal battery systems that can both heat and cool, such as reversible heat pumps and ground source heat pump (GSHP) systems. With dual-mode capability, your thermal battery can:

- Automatically switch between heating and cooling based on conditions
- Optimize both heating and cooling operations based on energy prices
- Leverage thermal inertia for both heating and cooling
- Take advantage of solar production for both operation modes
- Prevent rapid cycling between heating and cooling modes

Rather than manually switching between separate heating and cooling configurations based on season, the dual-mode approach allows a single configuration to handle both functions automatically throughout the year.
```

## 2. Configuration Parameters Section

Update the configuration parameters section to include dual-mode parameters:

```markdown
### Dual-Mode Configuration Parameters

To enable dual-mode operation, configure your thermal_battery with appropriate parameters for both heating and cooling:

#### Mode Control Parameters

* **dual_mode_enabled**: Enable dual-mode operation (default: true). Set to false for backward compatibility with heating-only operation.
  * Example: `true`

#### Temperature Parameters

* **heat_supply_temperature**: Heat pump supply temperature for heating mode in °C (water flowing from the heat pump).
  * Underfloor heating: typically 30-40°C
  * Radiators: typically 40-60°C
  * Example: `35.0`

* **cool_supply_temperature**: Heat pump supply temperature for cooling mode in °C.
  * Fan coils: typically 7-12°C
  * Chilled ceilings/floors: typically 15-18°C
  * Example: `12.0`

* **min_temperatures**: Minimum allowed temperatures in °C (list).
  * When heating: minimum comfort temperature, system will heat to maintain this
  * When cooling: lower bound that system won't cool below (over-cooling protection)
  * Example: `[20.0] * 48`

* **max_temperatures**: Maximum allowed temperatures in °C (list).
  * When heating: upper bound that system won't heat above
  * When cooling: maximum comfort temperature, system will cool to maintain this
  * Example: `[26.0] * 48`

#### Efficiency Parameters

* **heat_carnot_efficiency**: Real-world heat pump efficiency in heating mode as a fraction of the ideal Carnot cycle (default: 0.4).
  * Typical range: 0.35-0.45
  * Example: `0.4`

* **cool_carnot_efficiency**: Real-world heat pump efficiency in cooling mode as a fraction of the ideal Carnot cycle (default: 0.45).
  * Typically 5-10% higher than heating efficiency
  * Typical range: 0.4-0.55
  * Example: `0.45`

#### Anti-Cycling Parameters

* **min_runtime**: Minimum runtime once a mode is activated, in timesteps (default: 2).
  * Example: `2` (1 hour with 30-minute timesteps)

* **transition_cooldown**: Cooldown period between switching from one mode to another, in timesteps (default: 1).
  * Example: `1` (30 minutes with 30-minute timesteps)

* **max_mode_switches**: Maximum number of mode switches allowed in the optimization horizon (default: 6).
  * Example: `6` (for a 24-hour horizon)

* **switch_penalty**: Energy-equivalent penalty for mode switching in kWh (default: 0.1).
  * Example: `0.1`

#### Cooling-Specific Parameters

* **latent_cooling_factor**: Additional cooling energy needed for dehumidification, as a fraction of sensible cooling (default: 0.3).
  * Lower for dry climates (0.1-0.2)
  * Higher for humid climates (0.3-0.5)
  * Example: `0.3`
```

## 3. Example Configurations Section

Add example configurations specifically for dual-mode operation:

```markdown
### Dual-Mode Configuration Examples

#### Basic Dual-Mode Configuration

```json
"def_load_config": [
  {
    "thermal_battery": {
      "dual_mode_enabled": true,
      "heat_supply_temperature": 35.0,
      "cool_supply_temperature": 12.0,
      "heat_carnot_efficiency": 0.4,
      "cool_carnot_efficiency": 0.45,
      "volume": 20.0,
      "start_temperature": 22.0,
      "min_temperatures": [20.0] * 48,
      "max_temperatures": [26.0] * 48,
      "u_value": 0.5,
      "envelope_area": 400.0,
      "ventilation_rate": 0.5,
      "heated_volume": 300.0,
      "min_runtime": 2,
      "transition_cooldown": 1
    }
  }
]
```

#### Advanced Dual-Mode Configuration with Solar Gains

```json
"def_load_config": [
  {
    "thermal_battery": {
      "dual_mode_enabled": true,
      "heat_supply_temperature": 35.0,
      "cool_supply_temperature": 12.0,
      "heat_carnot_efficiency": 0.4,
      "cool_carnot_efficiency": 0.45,
      "volume": 20.0,
      "start_temperature": 22.0,
      "min_temperatures": [20.0] * 48,
      "max_temperatures": [26.0] * 48,
      "u_value": 0.5,
      "envelope_area": 400.0,
      "ventilation_rate": 0.5,
      "heated_volume": 300.0,
      "window_area": 40.0,
      "shgc": 0.6,
      "internal_gains_factor": 0.7,
      "min_runtime": 2,
      "transition_cooldown": 1,
      "max_mode_switches": 6,
      "latent_cooling_factor": 0.3
    }
  }
]
```

#### Seasonal Comfort Configuration

```json
"def_load_config": [
  {
    "thermal_battery": {
      "dual_mode_enabled": true,
      "heat_supply_temperature": 35.0,
      "cool_supply_temperature": 12.0,
      "heat_carnot_efficiency": 0.4,
      "cool_carnot_efficiency": 0.45,
      "volume": 20.0,
      "start_temperature": 22.0,
      // Winter comfort range: 20-23°C (first 24 timesteps)
      // Summer comfort range: 23-26°C (next 24 timesteps)
      "min_temperatures": [20.0] * 24 + [23.0] * 24,
      "max_temperatures": [23.0] * 24 + [26.0] * 24,
      "u_value": 0.5,
      "envelope_area": 400.0,
      "ventilation_rate": 0.5,
      "heated_volume": 300.0
    }
  }
]
```
```

## 4. How It Works Section

Add a section explaining how the dual-mode system works:

```markdown
## How Dual-Mode Operation Works

### Mode Selection Logic

The dual-mode thermal battery model allows the optimizer to automatically select between heating, cooling, or off at each timestep. The selection is based on:

1. **Temperature Requirements**: The optimizer will:
   - Activate heating if the temperature would fall below min_temperatures
   - Activate cooling if the temperature would rise above max_temperatures
   - Keep both modes off when temperature is comfortably within bounds

2. **Energy Costs**: Within the temperature constraints, the optimizer selects the most cost-effective operation:
   - May run heating during low-cost periods to pre-heat the thermal mass
   - May run cooling during high solar production to pre-cool the thermal mass
   - Avoids running either mode during high-cost periods when possible

3. **Anti-Cycling Protection**: The system prevents equipment damage by:
   - Ensuring a minimum runtime once a mode is activated
   - Enforcing a cooldown period when switching between modes
   - Limiting the total number of mode changes in the optimization horizon

### Energy Flow Model

The dual-mode model tracks energy flows accurately for both heating and cooling:

- **Heating Mode**: Heat pump adds energy to the thermal mass, increasing temperature
- **Cooling Mode**: Heat pump removes energy from the thermal mass, decreasing temperature
- **Solar Gains**: Heat entering through windows (increases cooling demand, reduces heating demand)
- **Internal Gains**: Heat from appliances and occupants (increases cooling demand, reduces heating demand)
- **Thermal Losses**: Heat exchange with outdoor environment (depends on temperature difference)

### COP Calculation

Coefficient of Performance (COP) is calculated separately for heating and cooling:

- **Heating COP**: Decreases as outdoor temperature drops
- **Cooling COP**: Decreases as outdoor temperature rises

This realistic modeling allows the optimizer to prefer operation during favorable outdoor temperature conditions.

### Temperature Dynamics

The temperature evolution follows this equation:

```
T[t+1] = T[t] + 
         (p_heat[t] * heat_cop[t] * conversion) -     // Heating effect
         (p_cool[t] * cool_cop[t] * conversion) -     // Cooling effect
         (thermal_losses[t] * conversion) -           // Thermal losses
         (heating_demand[t] * conversion) +           // Heating demand
         (cooling_demand[t] * conversion) +           // Cooling demand
         (solar_gains[t] * conversion)                // Solar gains
```

Where:
- `T[t]` is the temperature at time t
- `p_heat[t]` and `p_cool[t]` are the heating and cooling powers
- `heat_cop[t]` and `cool_cop[t]` are the COPs for each mode
- `conversion` is a factor converting kWh to temperature change
- `thermal_losses[t]` represents heat exchange with the environment
- `heating_demand[t]` and `cooling_demand[t]` represent building thermal demands
- `solar_gains[t]` represents solar heat through windows
```

## 5. Sensors and Home Assistant Integration

Add information about the dual-mode sensors:

```markdown
## Dual-Mode Sensors and Home Assistant Integration

The dual-mode thermal battery publishes a rich set of sensors to Home Assistant:

### Primary Sensors

* **sensor.p_heat{k}**: Heating power schedule (kW)
* **sensor.p_cool{k}**: Cooling power schedule (kW)
* **sensor.p_deferrable{k}**: Net thermal power (heating - cooling) for backward compatibility
* **sensor.temp_predicted{k}**: Predicted temperature (°C)
* **sensor.thermal_mode{k}**: Active mode (0=off, 1=heating, 2=cooling)
* **sensor.heating_demand{k}**: Calculated heating demand (kWh)
* **sensor.cooling_demand{k}**: Calculated cooling demand (kWh)

### Performance Sensors

* **sensor.cop_heat{k}**: Heating COP values
* **sensor.cop_cool{k}**: Cooling COP values
* **sensor.solar_gains{k}**: Solar heat gains (kWh)

### Thermal Inertia Sensors (when enabled)

* **sensor.q_input_heat{k}**: Filtered heating input (kWh)
* **sensor.q_input_cool{k}**: Filtered cooling input (kWh)

### Example Dashboard Cards

Create effective Home Assistant dashboards with these sensors:

```yaml
type: entities
title: Thermal System Status
entities:
  - entity: sensor.thermal_mode0
    name: Operating Mode
  - entity: sensor.temp_predicted0
    name: Predicted Temperature
  - entity: sensor.cop_heat0
    name: Heating Efficiency
  - entity: sensor.cop_cool0
    name: Cooling Efficiency
```

```yaml
type: custom:apexcharts-card
title: Thermal Power Schedule
series:
  - entity: sensor.p_heat0
    name: Heating Power
    color: "orange"
  - entity: sensor.p_cool0
    name: Cooling Power
    color: "blue"
  - entity: sensor.temp_predicted0
    name: Temperature
    yaxis_id: secondary
```
```

## 6. Troubleshooting Section

Add troubleshooting guidance for dual-mode operation:

```markdown
## Troubleshooting Dual-Mode Operation

### Common Issues and Solutions

#### System Never Activates Cooling

**Possible causes:**
- Maximum temperature is set too high
- Cooling supply temperature is too low for the heat pump model
- Cooling COP calculation is unrealistic

**Solutions:**
- Adjust max_temperatures to a more comfortable level
- Check cool_supply_temperature matches your heat pump specifications
- Increase cool_carnot_efficiency to a realistic value (0.4-0.55)

#### System Rapidly Switches Between Heating and Cooling

**Possible causes:**
- Anti-cycling parameters are too permissive
- Temperature comfort band (min to max) is too narrow

**Solutions:**
- Increase min_runtime parameter
- Increase transition_cooldown parameter
- Widen the gap between min_temperatures and max_temperatures

#### Poor Efficiency in Cooling Mode

**Possible causes:**
- Cool supply temperature is too low
- Cool carnot efficiency is set too low
- System is operating during hottest part of day

**Solutions:**
- Increase cool_supply_temperature to a more efficient level
- Adjust cool_carnot_efficiency based on manufacturer specifications
- Pre-cool during cooler parts of day to avoid peak outdoor temperatures

#### Optimization Problem Becomes Infeasible

**Possible causes:**
- Constraints are too restrictive
- Temperature comfort range is too narrow for the system capacity
- Anti-cycling constraints conflict with temperature requirements

**Solutions:**
- Widen the gap between min_temperatures and max_temperatures
- Ensure system has sufficient capacity for the building's thermal demands
- Reduce anti-cycling constraints (lower min_runtime or transition_cooldown)
```

## 7. Best Practices Section

Add guidance on best practices:

```markdown
## Dual-Mode Best Practices

### Optimal Configuration

1. **Temperature Ranges**:
   - Set min_temperatures 2-3°C below your heating setpoint
   - Set max_temperatures 2-3°C above your cooling setpoint
   - This provides the optimizer flexibility to minimize costs

2. **Supply Temperatures**:
   - For heating: Set as low as your distribution system allows
   - For cooling: Set as high as your distribution system allows
   - Both approaches maximize heat pump efficiency

3. **Anti-Cycling Parameters**:
   - Find the right balance between equipment protection and optimization flexibility
   - Typical heat pumps should run at least 20-30 minutes once started 
   - Allow 15-30 minutes between mode changes

4. **Efficiency Parameters**:
   - Calibrate carnot_efficiency values using real COP data from your heat pump
   - Compare actual performance to predicted values and adjust as needed

### Seasonal Considerations

1. **Winter Operation**:
   - System will primarily use heating mode
   - Pre-heating during low-cost periods is common
   - Consider lower min_temperatures at night for energy savings

2. **Summer Operation**:
   - System will primarily use cooling mode 
   - Pre-cooling during solar production periods maximizes self-consumption
   - Consider higher max_temperatures during unoccupied periods

3. **Shoulder Seasons**:
   - System may cycle between heating and cooling
   - Anti-cycling protection becomes especially important
   - Consider wider temperature comfort ranges

### Integration with Other Systems

1. **Solar PV Integration**:
   - The dual-mode system can function as an effective "thermal battery" for excess PV production
   - Heating or cooling can be activated to store energy as needed

2. **Home Assistant Automation**:
   - Use `sensor.thermal_mode{k}` to trigger mode-specific automations
   - Automate climate setpoints based on predicted temperatures

3. **Energy Management**:
   - Integrate heating and cooling power sensors with Home Assistant Energy Dashboard
   - Track efficiency and optimization performance over time
```

## 8. Migration Guide

Add guidance for users migrating from the single-mode approach:

```markdown
## Migrating from Single-Mode to Dual-Mode

If you are currently using a single-mode thermal_battery configuration (heating only), you can migrate to the dual-mode approach with these steps:

1. **Keep Existing Parameters**:
   - Retain all your existing thermal_battery parameters
   - Rename `supply_temperature` to `heat_supply_temperature` (or keep both for backward compatibility)
   - Rename `carnot_efficiency` to `heat_carnot_efficiency` (or keep both for backward compatibility)

2. **Add Cooling Parameters**:
   - Add `cool_supply_temperature` based on your heat pump specifications
   - Add `cool_carnot_efficiency` (typically 5-10% higher than heating efficiency)
   - Add the anti-cycling parameters as needed

3. **Enable Dual Mode**:
   - Add `"dual_mode_enabled": true` (though this is the default)

4. **Update Dashboards and Automations**:
   - Update any dashboards to use the new sensor names
   - Update automations to handle both heating and cooling modes

### Example Migration

**Before**:
```json
"thermal_battery": {
  "supply_temperature": 35.0,
  "carnot_efficiency": 0.4,
  "volume": 20.0,
  "start_temperature": 21.0,
  "min_temperatures": [20.0] * 48,
  "max_temperatures": [23.0] * 48,
  "u_value": 0.5,
  "envelope_area": 400.0,
  "ventilation_rate": 0.5,
  "heated_volume": 300.0
}
```

**After**:
```json
"thermal_battery": {
  "dual_mode_enabled": true,
  "heat_supply_temperature": 35.0,  // Renamed from supply_temperature
  "cool_supply_temperature": 12.0,  // Added for cooling
  "heat_carnot_efficiency": 0.4,    // Renamed from carnot_efficiency
  "cool_carnot_efficiency": 0.45,   // Added for cooling
  "volume": 20.0,
  "start_temperature": 21.0,
  "min_temperatures": [20.0] * 48,
  "max_temperatures": [26.0] * 48,  // Adjusted for cooling
  "u_value": 0.5,
  "envelope_area": 400.0,
  "ventilation_rate": 0.5,
  "heated_volume": 300.0,
  "min_runtime": 2,                 // Added for anti-cycling
  "transition_cooldown": 1          // Added for anti-cycling
}
```