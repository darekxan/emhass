# Unified Thermal Balance Model

EMHASS implements a unified thermal balance model for buildings that represents the natural physics of heat flow. This model provides a clean, physics-based approach to thermal modeling by using a single signed value to represent the building's thermal state.

## Physics Foundation

The thermal balance model is based on fundamental thermodynamic principles:

1. **Heat naturally flows from hot to cold**
2. **Energy is conserved**

These principles are represented mathematically as a signed thermal balance:

- **Positive Balance**: Building is losing heat to the environment (outdoor temperature < indoor temperature), heating required
- **Negative Balance**: Building is gaining heat from the environment (outdoor temperature > indoor temperature), cooling required
- **Zero Balance**: Building is in thermal equilibrium with environment (outdoor temperature = indoor temperature), no action required

## Mathematical Model

The thermal balance is calculated as:

$$
\text{Thermal Balance} = \text{Thermal Load} - \text{Solar Gains} - \text{Internal Gains}
$$

Where:

- **Thermal Load**: Heat flow through building envelope and ventilation, based on temperature difference
- **Solar Gains**: Heat input from solar radiation through windows
- **Internal Gains**: Heat generated from appliances, lighting, and occupants inside the building

### Detailed Formulation

The thermal load (conductive and convective heat flow) is calculated as:

$$
\text{Thermal Load} = U \cdot A \cdot (T_{indoor} - T_{outdoor}) + \dot{V} \cdot \rho \cdot c_p \cdot (T_{indoor} - T_{outdoor})
$$

Where:
- $U$ is the overall heat transfer coefficient (U-value) in W/(m²·K)
- $A$ is the envelope area in m²
- $\dot{V}$ is the ventilation rate in m³/h
- $\rho$ is air density (typically 1.2 kg/m³)
- $c_p$ is specific heat capacity of air (typically 1.005 kJ/(kg·K))
- $T_{indoor}$ is the indoor target temperature in °C
- $T_{outdoor}$ is the outdoor temperature in °C

The temperature difference $(T_{indoor} - T_{outdoor})$ is signed:
- Positive when indoor > outdoor → heat flows out → heating required
- Negative when outdoor > indoor → heat flows in → cooling required

## Heat Pump Operation

Heat pumps operate differently in heating versus cooling modes. The unified model automatically selects the appropriate coefficient of performance (COP) calculation based on the sign of the thermal balance:

### Heating Mode (Thermal Balance > 0)

$$
\text{COP}_{heat} = \eta_{carnot} \times \frac{T_{supply\_K}}{T_{supply\_K} - T_{outdoor\_K}}
$$

### Cooling Mode (Thermal Balance < 0)

$$
\text{COP}_{cool} = \eta_{carnot} \times \frac{T_{supply\_K}}{T_{outdoor\_K} - T_{supply\_K}}
$$

Where:
- $\eta_{carnot}$ is the Carnot efficiency factor (typically 0.35-0.5)
- $T_{supply\_K}$ is the supply temperature in Kelvin
- $T_{outdoor\_K}$ is the outdoor temperature in Kelvin

## Configuration Parameters

The thermal battery configuration with the unified model includes:

```json
{
  "thermal_config": {
    "thermal_efficiency": 5.0,        // Thermal input efficiency coefficient 
    "heat_loss_coefficient": 0.1,     // Building heat loss rate
    "thermal_inertia": 1.0,           // System response lag in hours
    "start_temperature": 20,          // Starting temperature
    "target_temperature": 21,         // Target temperature (can be array for multi-period)
    "heat_cop_params": {              // Heating COP parameters
      "supply_temperature": 35.0,     
      "carnot_efficiency": 0.4
    },
    "cool_cop_params": {              // Cooling COP parameters
      "supply_temperature": 12.0,
      "carnot_efficiency": 0.45
    },
    "max_heating_capacity": 5000,     // Maximum heating power (W)
    "max_cooling_capacity": 4200      // Maximum cooling power (W)
  }
}
```

## Advantages of the Unified Approach

1. **Physical Accuracy**: Directly models the continuity of thermal physics
2. **Optimization Efficiency**: Reduces the number of decision variables
3. **Intuitive Understanding**: Heat flow direction has physical meaning
4. **Cleaner Code**: Removes redundancy and complexity
5. **Flexible Response**: Seamlessly transitions between heating and cooling

## Example Usage

Here's an example of how to use the unified thermal model for optimization:

```yaml
rest_command:
  emhass_forecast:
    url: http://localhost:5000/action/naive-mpc-optim
    method: post
    timeout: 300
    headers:
      content-type: application/json
    payload: >
      {
        "prediction_horizon": 24,
        "load_cost_forecast": {{ (state_attr('sensor.electricity_price_forecast', 'forecasts') | map(attribute='currency_per_kWh') | list)[:24] | tojson }},
        "outdoor_temperature_forecast": {{ (state_attr("sensor.weather_hourly", "forecast") | map(attribute="temperature") | list)[:24] | tojson }},
        "ghi_forecast": {{ (state_attr("sensor.weather_hourly", "forecast") | map(attribute="irradiance") | list)[:24] | tojson }},
        "def_load_config": [
          {
            "thermal_config": {
              "thermal_efficiency": 5.0,
              "heat_loss_coefficient": 0.1,
              "thermal_inertia": 1.0,
              "start_temperature": {{ states('sensor.room_temperature') }},
              "target_temperature": 22.0,
              "heat_cop_params": {
                "supply_temperature": 35.0,
                "carnot_efficiency": 0.4
              },
              "cool_cop_params": {
                "supply_temperature": 15.0,
                "carnot_efficiency": 0.45
              },
              "max_heating_capacity": 4000,
              "max_cooling_capacity": 3500
            }
          }
        ]
      }
```

## Visualization

The thermal balance can be visualized with a signed value chart:
- Positive values (typically displayed in red) indicate heating demand
- Negative values (typically displayed in blue) indicate cooling demand
- Zero line represents thermal equilibrium

This approach provides an intuitive view of building thermal behavior across all seasons and conditions.