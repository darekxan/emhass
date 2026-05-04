# Sensor Publishing for Thermal Battery Cooling Mode

## Current Sensor Publishing

Currently, the thermal_battery component publishes several sensors to Home Assistant:

1. `sensor.p_deferrable{k}` - The scheduled power for the heat pump
2. `sensor.temp_predicted{k}` - The predicted temperature of the thermal mass
3. `sensor.heating_demand{k}` - The calculated heating demand
4. `sensor.q_input_heater{k}` - Filtered heat input (when thermal inertia is enabled)

These sensor names and the underlying data they represent need to be modified to properly support cooling mode.

## Required Changes

### 1. Rename/Clarify Sensors Based on Mode

We need to update the naming, descriptions, and attributes of sensors to clarify whether they represent heating or cooling operations.

For `sensor.heating_demand{k}`:
- This sensor name is specific to heating mode
- For consistency, we should either:
  - Keep the name but add a mode attribute
  - OR rename the sensor dynamically based on mode

### 2. Add Mode Attribute to All Thermal Battery Sensors

Each thermal battery sensor should include a `mode` attribute indicating if it's operating in "heat" or "cool" mode. This will make it clear to users which mode the system is in and help with automation and visualization.

### 3. Update Unit of Measurement for Cooling

The unit for cooling demand should be consistent with heating demand (kWh), but the sense needs to be made clear in the sensor's friendly_name or attributes.

### 4. Add New Cooling-Specific Attributes

Consider adding cooling-specific attributes such as:
- Cooling efficiency (COP)
- Energy consumed for cooling
- Cooling performance metrics

## Implementation Changes

### File: `src/emhass/web_server.py`

The main sensor publishing logic is in `web_server.py`. We need to modify the sensor registration to account for cooling mode:

```python
def _publish_thermal_battery_results(self, k, p_def_vals, sens_temps, heat_demand, solar_gains, q_inputs=None):
    """Publish thermal battery results to Home Assistant"""
    # Get sense parameter from optimization config
    sense = self.optim.optim_conf["def_load_config"][k]["thermal_battery"].get("sense", "heat")
    
    # Common attributes for all thermal battery sensors
    common_attrs = {
        "mode": sense,
        "thermal_battery": "true",
    }
    
    # Publish power schedule
    sensor_name = f"p_deferrable{k}"
    friendly_name = f"{'Cooling' if sense == 'cool' else 'Heating'} Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "icon": "mdi:flash",
    }
    self._publish_sensor(sensor_name, p_def_vals, attrs)
    
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
    
    # Publish demand
    sensor_name = f"thermal_demand{k}"
    demand_type = "Cooling" if sense == "cool" else "Heating"
    friendly_name = f"{demand_type} Demand {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "icon": "mdi:radiator" if sense == "heat" else "mdi:snowflake",
    }
    self._publish_sensor(sensor_name, heat_demand, attrs)
    
    # Publish solar gains
    sensor_name = f"solar_gains{k}"
    friendly_name = f"Solar Gains {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "icon": "mdi:weather-sunny",
        "impact": "reduces demand" if sense == "heat" else "increases demand",
    }
    self._publish_sensor(sensor_name, solar_gains, attrs)
    
    # Publish filtered heat input if thermal inertia is enabled
    if q_inputs is not None:
        sensor_name = f"q_input_thermal{k}"
        friendly_name = f"{'Cooling' if sense == 'cool' else 'Heating'} Thermal Input {k}"
        attrs = {
            **common_attrs,
            "friendly_name": friendly_name,
            "unit_of_measurement": "kWh",
            "icon": "mdi:radiator" if sense == "heat" else "mdi:snowflake",
        }
        self._publish_sensor(sensor_name, q_inputs, attrs)
```

### Backward Compatibility

To maintain backward compatibility with existing automations and configurations:
1. Continue to publish `heating_demand{k}` for all thermal batteries, but with clear mode attributes
2. Add new `thermal_demand{k}` sensors that are mode-neutral
3. Document the changes and recommend users update to the new sensors

## User Interface Experience

With these changes, users will be able to:

1. Clearly distinguish between heating and cooling operations in the Home Assistant UI
2. Use appropriate icons for each mode (e.g., snowflake for cooling)
3. Track performance metrics specific to each mode
4. Create accurate visualizations and dashboards for their thermal systems

These sensor publishing changes ensure that users can effectively monitor and automate both heating and cooling modes of their thermal battery systems.