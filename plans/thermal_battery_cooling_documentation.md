# Thermal Battery Documentation Update for Cooling Mode

The following is a draft of the cooling mode section to be added to the `docs/thermal_battery.md` file. This content should be inserted as a new section after the existing parameter documentation and before the example configurations.

```markdown
## Cooling Mode Support

The thermal battery model now supports cooling operation in addition to heating. This is particularly useful for heat pump systems that can operate in both modes, such as ground source heat pumps (GSHP) and reversible air-to-water heat pumps. With cooling mode support, you can optimize cooling operation based on:

- Variable electricity pricing (run cooling during cheap periods)
- Solar PV production (use excess solar energy for cooling)
- Building thermal inertia (pre-cool during low-cost periods)
- Heat pump efficiency variations with outdoor temperature

### Configuring Cooling Mode

To enable cooling mode for a thermal battery, add the `sense` parameter with value `"cool"` to your thermal_battery configuration:

```json
"thermal_battery": {
  "sense": "cool",
  "supply_temperature": 12.0,
  ...other parameters...
}
```

When `sense` is set to `"cool"`, all the thermal battery parameters are interpreted in the context of cooling operation instead of heating.

### Parameter Adjustments for Cooling Mode

While most parameters serve the same function in both heating and cooling modes, there are some important adjustments to consider:

* **supply_temperature**: In cooling mode, this is the cold water supply temperature (typically 7-15°C), whereas in heating it's the warm water supply temperature (typically 30-50°C).
  * Lower values = better cooling efficiency
  * Example: `12.0` for underfloor cooling or `7.0` for fan coil units

* **min_temperatures**: In cooling mode, this represents the minimum comfortable temperature - the system will not cool below this threshold.
  * Sometimes referred to as "overcooling protection"
  * Example: `[20.0] * 48` (prevent cooling below 20°C)

* **max_temperatures**: In cooling mode, this represents the maximum allowable temperature - the temperature at which cooling will definitely operate.
  * The primary comfort limit for cooling
  * Example: `[26.0] * 48` (cool when temperature reaches 26°C)

* **carnot_efficiency**: Cooling operation often has higher efficiency than heating.
  * Typical range for cooling: 0.40-0.55
  * Example: `0.45`

### Physics-Based Cooling Demand

When using the physics-based model (u_value, envelope_area, etc.), the cooling demand calculation changes in important ways:

1. **Temperature difference**: Cooling demand increases when outdoor temperature is higher than indoor temperature (opposite of heating)
2. **Solar gains**: In cooling mode, solar gains through windows increase cooling demand (whereas they reduce heating demand)
3. **Internal gains**: Electrical appliances and occupants generate heat, which increases cooling demand

This means that the same building will show different behavior in cooling mode compared to heating mode.

### Example Cooling Configuration

Here's a complete example configuration for a thermal battery in cooling mode:

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
      "heated_volume": 300.0,
      "window_area": 30.0,
      "shgc": 0.6,
      "internal_gains_factor": 0.7
    }
  }
]
```

### How Cooling Optimization Works

In cooling mode, the optimizer:

1. Models how the indoor temperature rises due to outdoor temperature, solar gains, and internal gains
2. Calculates when cooling needs to operate to keep the temperature below the maximum threshold
3. Takes into account varying electricity prices and PV production
4. Considers the heat pump's COP, which varies with outdoor temperature
5. Finds the most cost-effective schedule for cooling operation

#### Optimization Strategies

The optimization might employ several strategies:

* **Pre-cooling**: Cool the building during low-cost periods, taking advantage of thermal mass
* **Solar self-consumption**: Coordinate cooling with solar PV production
* **COP optimization**: Prefer cooling during times with favorable outdoor temperatures

### What Sensors Get Published

When using a thermal battery in cooling mode, the following sensors will be published to Home Assistant:

* **sensor.p_deferrable{k}**: Power schedule for the cooling device
* **sensor.temp_predicted{k}**: Predicted indoor temperature
* **sensor.thermal_demand{k}**: Calculated cooling demand
* **sensor.solar_gains{k}**: Solar heat gains through windows
* **sensor.q_input_thermal{k}**: Filtered cooling input (when thermal inertia is enabled)

Each sensor includes a `mode` attribute set to `"cool"` to distinguish it from heating operation.

### Troubleshooting Cooling Mode

Some common issues when setting up cooling mode:

1. **Insufficient cooling capacity**: If the system never reaches the desired max_temperature, your heat pump nominal power may be too low or your comfort range too tight.

2. **Supply temperature too high**: In cooling mode, an efficient heat pump should have a supply temperature of 7-15°C. Setting this too high will result in poor cooling efficiency.

3. **Unexpected COP values**: Very high outdoor temperatures can result in poor COP values. This is normal physics - cooling becomes harder as outdoor temperatures increase.

4. **Pre-cooling behavior**: If the system pre-cools too aggressively, you may want to tighten the temperature range between min_temperatures and max_temperatures.

### Advanced: Combined Heating and Cooling

To model a system that can perform both heating and cooling depending on the season, you would typically:

1. Configure two separate thermal batteries - one for heating and one for cooling
2. Activate the appropriate thermal battery based on the season or outdoor temperature forecast
3. Use Home Assistant automations to switch between the two modes
```

This documentation update comprehensively covers all aspects of the new cooling mode functionality, providing users with the information they need to effectively configure and troubleshoot their cooling systems.