# Sensor Publishing for Dual-Mode Thermal Battery

This document outlines the implementation of sensor publishing for the dual-mode thermal battery component in EMHASS, detailing how optimization results will be exposed to Home Assistant for monitoring and automation.

## 1. Current Sensor Publishing Implementation

Currently, the thermal battery publishes sensors like:

- `sensor.p_deferrable{k}`: Power schedule for the thermal load
- `sensor.temp_predicted{k}`: Predicted temperature for the thermal mass
- `sensor.heating_demand{k}`: Calculated heating demand
- `sensor.q_input_heater{k}`: Filtered thermal input (when thermal inertia is enabled)

For dual-mode operation, we need to enhance this to support both heating and cooling operations with clear distinctions.

## 2. Dual-Mode Sensor Design

Our enhanced sensor publishing will include:

### 2.1. Power Sensors

```python
# Heating power sensor
sensor_name = f"p_heat{k}"
friendly_name = f"Heating Power Schedule {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kW",
    "device_class": "power",
    "icon": "mdi:radiator",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "heating"
}
self._publish_sensor(sensor_name, p_heat_vals, attrs)

# Cooling power sensor
sensor_name = f"p_cool{k}"
friendly_name = f"Cooling Power Schedule {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kW",
    "device_class": "power",
    "icon": "mdi:snowflake",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "cooling"
}
self._publish_sensor(sensor_name, p_cool_vals, attrs)

# Net power sensor (backward compatibility)
sensor_name = f"p_deferrable{k}"
friendly_name = f"Net Thermal Power Schedule {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kW",
    "device_class": "power",
    "icon": "mdi:hvac",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "net"
}
self._publish_sensor(sensor_name, net_power_vals, attrs)
```

### 2.2. Temperature and Mode Sensors

```python
# Predicted temperature sensor
sensor_name = f"temp_predicted{k}"
friendly_name = f"Predicted Temperature {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "°C",
    "device_class": "temperature",
    "icon": "mdi:thermometer",
    "thermal_battery": "true",
    "dual_mode": "true"
}
self._publish_sensor(sensor_name, sens_temps, attrs)

# Active mode sensor
sensor_name = f"thermal_mode{k}"
friendly_name = f"Thermal Mode {k}"
attrs = {
    "friendly_name": friendly_name,
    "icon": "mdi:hvac",
    "thermal_battery": "true",
    "dual_mode": "true",
    "states": {
        "0": "off",
        "1": "heating",
        "2": "cooling"
    }
}
self._publish_sensor(sensor_name, mode_vals, attrs)
```

### 2.3. Demand Sensors

```python
# Heating demand sensor
sensor_name = f"heating_demand{k}"
friendly_name = f"Heating Demand {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "icon": "mdi:radiator",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "heating"
}
self._publish_sensor(sensor_name, heat_demand, attrs)

# Cooling demand sensor
sensor_name = f"cooling_demand{k}"
friendly_name = f"Cooling Demand {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "icon": "mdi:snowflake",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "cooling"
}
self._publish_sensor(sensor_name, cool_demand, attrs)
```

### 2.4. Energy Efficiency Sensors

```python
# Heating COP sensor
sensor_name = f"cop_heat{k}"
friendly_name = f"Heating COP {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "",
    "icon": "mdi:chart-efficiency",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "heating"
}
self._publish_sensor(sensor_name, heat_cops, attrs)

# Cooling COP sensor
sensor_name = f"cop_cool{k}"
friendly_name = f"Cooling COP {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "",
    "icon": "mdi:chart-efficiency",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "cooling"
}
self._publish_sensor(sensor_name, cool_cops, attrs)
```

### 2.5. Thermal Inertia Sensors

For systems with thermal inertia enabled:

```python
# Heating input filter sensor
sensor_name = f"q_input_heat{k}"
friendly_name = f"Heating Thermal Input {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "icon": "mdi:radiator",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "heating"
}
self._publish_sensor(sensor_name, q_heat_inputs, attrs)

# Cooling input filter sensor
sensor_name = f"q_input_cool{k}"
friendly_name = f"Cooling Thermal Input {k}"
attrs = {
    "friendly_name": friendly_name,
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "icon": "mdi:snowflake",
    "thermal_battery": "true",
    "dual_mode": "true",
    "operation": "cooling"
}
self._publish_sensor(sensor_name, q_cool_inputs, attrs)
```

## 3. Implementation in Web Server

### 3.1. New Method for Dual-Mode Sensor Publishing

```python
def _publish_dual_mode_thermal_battery_results(
    self, k, p_heat_vals, p_cool_vals, mode_vals, sens_temps, 
    heat_demand, cool_demand, heat_cops, cool_cops, solar_gains, 
    q_heat_inputs=None, q_cool_inputs=None
):
    """
    Publish dual-mode thermal battery results to Home Assistant.
    
    :param k: Deferrable load index
    :param p_heat_vals: Array of heating power values (kW)
    :param p_cool_vals: Array of cooling power values (kW)
    :param mode_vals: Array of mode values (0=off, 1=heating, 2=cooling)
    :param sens_temps: Array of predicted temperatures (°C)
    :param heat_demand: Array of heating demand values (kWh)
    :param cool_demand: Array of cooling demand values (kWh)
    :param heat_cops: Array of heating COP values
    :param cool_cops: Array of cooling COP values
    :param solar_gains: Array of solar gain values (kWh)
    :param q_heat_inputs: Array of filtered heating input values (kWh), optional
    :param q_cool_inputs: Array of filtered cooling input values (kWh), optional
    """
    # Common attributes for all thermal battery sensors
    common_attrs = {
        "thermal_battery": "true",
        "dual_mode": "true",
    }
    
    # Calculate net power (heating - cooling) for backward compatibility
    net_power_vals = p_heat_vals - p_cool_vals
    
    # --- Power Sensors ---
    
    # Heating power sensor
    sensor_name = f"p_heat{k}"
    friendly_name = f"Heating Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "device_class": "power",
        "icon": "mdi:radiator",
        "operation": "heating"
    }
    self._publish_sensor(sensor_name, p_heat_vals, attrs)
    
    # Cooling power sensor
    sensor_name = f"p_cool{k}"
    friendly_name = f"Cooling Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "device_class": "power",
        "icon": "mdi:snowflake",
        "operation": "cooling"
    }
    self._publish_sensor(sensor_name, p_cool_vals, attrs)
    
    # Net power sensor (backward compatibility)
    sensor_name = f"p_deferrable{k}"
    friendly_name = f"Net Thermal Power Schedule {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kW",
        "device_class": "power",
        "icon": "mdi:hvac",
        "operation": "net"
    }
    self._publish_sensor(sensor_name, net_power_vals, attrs)
    
    # --- Temperature and Mode Sensors ---
    
    # Predicted temperature sensor
    sensor_name = f"temp_predicted{k}"
    friendly_name = f"Predicted Temperature {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "icon": "mdi:thermometer"
    }
    self._publish_sensor(sensor_name, sens_temps, attrs)
    
    # Active mode sensor
    sensor_name = f"thermal_mode{k}"
    friendly_name = f"Thermal Mode {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "icon": "mdi:hvac",
        "states": {
            "0": "off",
            "1": "heating",
            "2": "cooling"
        }
    }
    self._publish_sensor(sensor_name, mode_vals, attrs)
    
    # --- Demand Sensors ---
    
    # Heating demand sensor
    sensor_name = f"heating_demand{k}"
    friendly_name = f"Heating Demand {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "icon": "mdi:radiator",
        "operation": "heating"
    }
    self._publish_sensor(sensor_name, heat_demand, attrs)
    
    # Cooling demand sensor
    sensor_name = f"cooling_demand{k}"
    friendly_name = f"Cooling Demand {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "icon": "mdi:snowflake",
        "operation": "cooling"
    }
    self._publish_sensor(sensor_name, cool_demand, attrs)
    
    # Solar gains sensor
    sensor_name = f"solar_gains{k}"
    friendly_name = f"Solar Heat Gains {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "icon": "mdi:weather-sunny"
    }
    self._publish_sensor(sensor_name, solar_gains, attrs)
    
    # --- Efficiency Sensors ---
    
    # Heating COP sensor
    sensor_name = f"cop_heat{k}"
    friendly_name = f"Heating COP {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "",
        "icon": "mdi:chart-efficiency",
        "operation": "heating"
    }
    self._publish_sensor(sensor_name, heat_cops, attrs)
    
    # Cooling COP sensor
    sensor_name = f"cop_cool{k}"
    friendly_name = f"Cooling COP {k}"
    attrs = {
        **common_attrs,
        "friendly_name": friendly_name,
        "unit_of_measurement": "",
        "icon": "mdi:chart-efficiency",
        "operation": "cooling"
    }
    self._publish_sensor(sensor_name, cool_cops, attrs)
    
    # --- Thermal Inertia Sensors (if enabled) ---
    
    if q_heat_inputs is not None:
        sensor_name = f"q_input_heat{k}"
        friendly_name = f"Heating Thermal Input {k}"
        attrs = {
            **common_attrs,
            "friendly_name": friendly_name,
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "icon": "mdi:radiator",
            "operation": "heating"
        }
        self._publish_sensor(sensor_name, q_heat_inputs, attrs)
    
    if q_cool_inputs is not None:
        sensor_name = f"q_input_cool{k}"
        friendly_name = f"Cooling Thermal Input {k}"
        attrs = {
            **common_attrs,
            "friendly_name": friendly_name,
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "icon": "mdi:snowflake",
            "operation": "cooling"
        }
        self._publish_sensor(sensor_name, q_cool_inputs, attrs)
```

### 3.2. Mode Value Conversion

For the mode sensor, we need to convert binary variables to mode values:

```python
# Calculate mode values from binary variables
# 0 = off, 1 = heating, 2 = cooling
def _calculate_mode_values(heat_active, cool_active):
    """
    Convert binary heating and cooling activation arrays to mode values.
    
    :param heat_active: Binary heating activation array
    :param cool_active: Binary cooling activation array
    :return: Array of mode values (0=off, 1=heating, 2=cooling)
    """
    mode_vals = np.zeros_like(heat_active)
    mode_vals[heat_active > 0.5] = 1  # Heating mode
    mode_vals[cool_active > 0.5] = 2  # Cooling mode
    return mode_vals
```

### 3.3. Enhanced Result Extraction

In `web_server.py`, the result extraction needs to be updated:

```python
def _extract_dual_mode_results(self, k, results, required_len):
    """
    Extract dual-mode thermal battery results from optimization results.
    
    :param k: Deferrable load index
    :param results: Optimization results dictionary
    :param required_len: Required length of result arrays
    :return: Tuple of extracted arrays
    """
    # Get standard values
    p_heat = results.get(f'p_heat{k}', np.zeros(required_len))
    p_cool = results.get(f'p_cool{k}', np.zeros(required_len))
    heat_active = results.get(f'heat_active{k}', np.zeros(required_len))
    cool_active = results.get(f'cool_active{k}', np.zeros(required_len))
    sens_temps = results.get(f'temp_predicted{k}', np.zeros(required_len))
    
    # Calculate mode values
    mode_vals = self._calculate_mode_values(heat_active, cool_active)
    
    # Get COP values
    heat_cops = self.optim.param_thermal[k]["heat_cops"].value
    cool_cops = self.optim.param_thermal[k]["cool_cops"].value
    
    # Get demand values
    heat_demand = self.optim.param_thermal[k]["heating_demand"].value
    cool_demand = self.optim.param_thermal[k]["cooling_demand"].value
    solar_gains = self.optim.param_thermal[k]["solar_gains"].value
    
    # Get thermal inertia values if available
    q_heat_inputs = None
    q_cool_inputs = None
    if f'q_heat_input_{k}' in self.optim.vars:
        q_heat_inputs = results.get(f'q_heat_input_{k}', np.zeros(required_len))
    if f'q_cool_input_{k}' in self.optim.vars:
        q_cool_inputs = results.get(f'q_cool_input_{k}', np.zeros(required_len))
    
    return (p_heat, p_cool, mode_vals, sens_temps, heat_demand, cool_demand,
            heat_cops, cool_cops, solar_gains, q_heat_inputs, q_cool_inputs)
```

### 3.4. Integration with Publish Data

Update the `publish_data` method to handle dual-mode thermal batteries:

```python
def publish_data(self):
    # ... (existing code)
    
    # Process each deferrable load
    for k in range(num_def_loads):
        # ... (existing code for standard deferrable loads)
        
        # For dual-mode thermal battery
        if (
            "def_load_config" in self.optim_conf
            and len(self.optim_conf["def_load_config"]) > k
            and "thermal_battery" in self.optim_conf["def_load_config"][k]
            and self.optim_conf["def_load_config"][k]["thermal_battery"].get("dual_mode_enabled", True)
        ):
            # Extract results
            (p_heat, p_cool, mode_vals, sens_temps, heat_demand, cool_demand,
             heat_cops, cool_cops, solar_gains, q_heat_inputs, q_cool_inputs) = self._extract_dual_mode_results(
                k, results, required_len)
            
            # Publish dual-mode results
            self._publish_dual_mode_thermal_battery_results(
                k, p_heat, p_cool, mode_vals, sens_temps, 
                heat_demand, cool_demand, heat_cops, cool_cops, solar_gains,
                q_heat_inputs, q_cool_inputs)
            
        # For legacy thermal battery (single mode)
        elif (
            "def_load_config" in self.optim_conf
            and len(self.optim_conf["def_load_config"]) > k
            and "thermal_battery" in self.optim_conf["def_load_config"][k]
        ):
            # Use existing thermal battery publishing
            # ... (existing thermal battery publishing code)
    
    # ... (rest of method)
```

## 4. Dashboard Integration

Home Assistant dashboards can be created to visualize the dual-mode operation using these sensors. Here's an example of panels that could be created:

### 4.1. Mode Status Card

```yaml
type: entities
title: Thermal System Status
entities:
  - entity: sensor.thermal_mode0
    name: Operating Mode
    icon: mdi:hvac
  - entity: sensor.temp_predicted0
    name: Predicted Temperature
  - entity: sensor.cop_heat0
    name: Heating Efficiency (COP)
    show_when: heating
  - entity: sensor.cop_cool0
    name: Cooling Efficiency (COP)
    show_when: cooling
```

### 4.2. Power Schedule Graph

```yaml
type: custom:apexcharts-card
title: Thermal Power Schedule
header:
  show: true
  title: Thermal Power Schedule
  show_states: true
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

### 4.3. Demand Graph

```yaml
type: custom:apexcharts-card
title: Thermal Demand
header:
  show: true
  title: Thermal Demand
  show_states: true
series:
  - entity: sensor.heating_demand0
    name: Heating Demand
    color: "orange"
  - entity: sensor.cooling_demand0
    name: Cooling Demand
    color: "blue"
  - entity: sensor.solar_gains0
    name: Solar Gains
    color: "yellow"
```

## 5. Configuration Parameter for Web Server

Add a configuration parameter to control the detailed sensor publishing:

```json
"hass_connect": {
  // ...
  "publish_detailed_thermal_sensors": true  // Default: true
}
```

If set to `false`, only the essential sensors will be published to reduce the number of entities in Home Assistant.

## 6. Energy Management Integration

The dual-mode sensors support Home Assistant Energy Management integration:

```yaml
energy:
  device_consumption:
    - entity_id: sensor.p_heat0
      name: Heating Energy
      unique_id: heating_energy_consumption
    - entity_id: sensor.p_cool0
      name: Cooling Energy
      unique_id: cooling_energy_consumption
```

This allows tracking heating and cooling energy consumption separately in the Home Assistant Energy Dashboard.

## 7. Future Extensions

Future enhancements to sensor publishing could include:

1. **Energy Cost Sensors**: Separate sensors for heating and cooling costs
2. **Performance Metrics**: Sensors for COP efficiency reporting
3. **Comfort Metrics**: Sensors for tracking comfort within desired temperature ranges
4. **Mode Prediction**: Sensors predicting future mode transitions

## 8. Implementation Timeline

1. Implement basic dual-mode sensor publishing
2. Add mode tracking sensors
3. Add efficiency and performance sensors 
4. Create example dashboard configurations
5. Add enhanced energy management integration