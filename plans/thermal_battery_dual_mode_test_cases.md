# Test Cases for Dual-Mode Thermal Battery

This document outlines the key test cases needed to verify the dual-mode thermal battery implementation.

## 1. Core Component Tests

### 1.1. Dual COP Calculation Tests

```python
def test_calculate_cop_dual_mode():
    """Test the dual-mode COP calculation."""
    # Test heating and cooling COPs under various outdoor temperatures
    heat_supply_temp = 35.0
    cool_supply_temp = 12.0
    heat_eff = 0.4
    cool_eff = 0.45
    
    # Test with varied outdoor temperatures
    outdoor_temps = np.array([0.0, 10.0, 20.0, 30.0, 35.0])
    
    heat_cops, cool_cops = utils.calculate_cop_dual_mode(
        heat_supply_temperature=heat_supply_temp,
        cool_supply_temperature=cool_supply_temp,
        heat_carnot_efficiency=heat_eff,
        cool_carnot_efficiency=cool_eff,
        outdoor_temperature_forecast=outdoor_temps,
    )
    
    # Verify heating COPs
    # Lower outdoor temps = lower heating COP
    assert np.all(np.diff(heat_cops[:4]) > 0)  # COPs should increase with temperature
    assert heat_cops[4] == 1.0  # When outdoor > supply, COP should default to 1.0
    
    # Verify cooling COPs
    # Higher outdoor temps = lower cooling COP
    assert cool_cops[0] == 1.0  # When outdoor < supply, COP should default to 1.0
    assert cool_cops[1] == 1.0  # When outdoor < supply, COP should default to 1.0
    assert np.all(np.diff(cool_cops[2:]) < 0)  # COPs should decrease with temperature
```

### 1.2. Dual Thermal Demand Tests

```python
def test_calculate_dual_thermal_demand():
    """Test the dual thermal demand calculation."""
    # Test parameters
    u_value = 0.5
    envelope_area = 400.0
    ventilation_rate = 0.5
    heated_volume = 300.0
    indoor_target_temp = 22.0
    time_step = 30
    
    # Test with both cold and hot outdoor temperatures
    outdoor_temps = np.array([10.0, 15.0, 20.0, 25.0, 30.0])
    
    # Calculate dual demand
    demands = utils.calculate_dual_thermal_demand(
        u_value=u_value,
        envelope_area=envelope_area,
        ventilation_rate=ventilation_rate,
        heated_volume=heated_volume,
        indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temps,
        optimization_time_step=time_step,
    )
    
    # Verify heating demand is positive when outdoor < indoor
    assert np.all(demands["heating_demand_kwh"][:3] > 0)
    assert np.all(demands["heating_demand_kwh"][3:] == 0)
    
    # Verify cooling demand is positive when outdoor > indoor
    assert np.all(demands["cooling_demand_kwh"][:2] == 0)
    assert np.all(demands["cooling_demand_kwh"][2:] > 0)
    
    # Verify solar gains with window area
    window_area = 40.0
    solar_irradiance = np.array([100.0, 300.0, 500.0, 700.0, 900.0])
    
    demands_with_solar = utils.calculate_dual_thermal_demand(
        u_value=u_value,
        envelope_area=envelope_area,
        ventilation_rate=ventilation_rate,
        heated_volume=heated_volume,
        indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temps,
        optimization_time_step=time_step,
        solar_irradiance_forecast=solar_irradiance,
        window_area=window_area,
        shgc=0.6,
    )
    
    # Solar gains should reduce heating demand and increase cooling demand
    assert np.all(demands_with_solar["heating_demand_kwh"][:3] < demands["heating_demand_kwh"][:3])
    assert np.all(demands_with_solar["cooling_demand_kwh"][2:] > demands["cooling_demand_kwh"][2:])
```

## 2. System Integration Tests

### 2.1. Dual-Mode Optimization Test

```python
def test_dual_mode_thermal_battery_optimization():
    """Test the full optimization with dual-mode thermal battery."""
    # Create test configuration
    optim_conf = {
        "prediction_horizon": 8,
        "def_total_hours": 4,
        "def_load_config": [
            {
                "thermal_battery": {
                    "dual_mode_enabled": True,
                    "heat_supply_temperature": 35.0,
                    "cool_supply_temperature": 12.0,
                    "heat_carnot_efficiency": 0.4,
                    "cool_carnot_efficiency": 0.45,
                    "volume": 20.0,
                    "start_temperature": 22.0,
                    "min_temperatures": [20.0] * 8,
                    "max_temperatures": [26.0] * 8,
                    "u_value": 0.5,
                    "envelope_area": 400.0,
                    "ventilation_rate": 0.5,
                    "heated_volume": 300.0,
                    "min_runtime": 2,
                    "transition_cooldown": 1
                }
            }
        ],
        "nominal_power_of_deferrable_loads": [3.0],
        "treat_deferrable_load_as_semi_cont": [True],
        "load_cost_forecast": [0.1, 0.2, 0.3, 0.2, 0.1, 0.2, 0.3, 0.2]
    }
    
    # Create test data with varied outdoor temperatures
    # First half cold, second half hot - should trigger both modes
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=8, freq='30min'),
        'load_power': [0.5] * 8,
        'pv_power': [0.0] * 8,
        'outdoor_temperature': [10.0, 12.0, 14.0, 16.0, 24.0, 26.0, 28.0, 30.0]
    })
    
    # Run optimization
    optimizer = Optimization()
    optimizer.optim_conf = optim_conf
    result = optimizer.perform_optimization(test_data)
    
    # Verify successful optimization
    assert result['optim_status'] == 'optimal'
    
    # Verify both heating and cooling were used
    assert np.any(result.get('p_heat0', np.zeros(8)) > 0)
    assert np.any(result.get('p_cool0', np.zeros(8)) > 0)
    
    # Verify temperature stays within bounds
    assert np.all(result['temp_predicted0'] <= 26.0)
    assert np.all(result['temp_predicted0'] >= 20.0)
    
    # Verify anti-cycling constraints were respected
    # No rapid oscillation between heating and cooling
    heat_starts = np.diff(np.concatenate(([0], result.get('heat_active0', np.zeros(8)))))
    cool_starts = np.diff(np.concatenate(([0], result.get('cool_active0', np.zeros(8)))))
    
    # Count mode activations
    heat_activations = np.sum(heat_starts > 0)
    cool_activations = np.sum(cool_starts > 0)
    
    # Verify reasonable number of activations for short horizon
    assert heat_activations <= 2
    assert cool_activations <= 2
```

### 2.2. Sensor Publishing Test

```python
def test_dual_mode_sensor_publishing():
    """Test sensor publishing for dual-mode thermal battery."""
    # Mock the web server and optimization
    web_server = create_test_web_server()
    
    # Set up a dual-mode configuration
    web_server.optim.optim_conf = {
        "def_load_config": [
            {
                "thermal_battery": {
                    "dual_mode_enabled": True,
                    "heat_supply_temperature": 35.0,
                    "cool_supply_temperature": 12.0
                }
            }
        ]
    }
    
    # Create test data
    p_heat = [1.5, 0.0, 0.0]
    p_cool = [0.0, 0.0, 2.0]
    mode_vals = [1, 0, 2]  # 1=heating, 0=off, 2=cooling
    sens_temps = [21.0, 22.0, 23.0]
    heat_demand = [0.5, 0.2, 0.0]
    cool_demand = [0.0, 0.3, 0.7]
    heat_cops = [3.0, 3.2, 3.5]
    cool_cops = [4.0, 3.8, 3.5]
    solar_gains = [0.1, 0.2, 0.3]
    
    # Mock the publish_sensor method
    with mock.patch.object(web_server, '_publish_sensor') as mock_publish:
        # Call the method to test
        web_server._publish_dual_mode_thermal_battery_results(
            0, p_heat, p_cool, mode_vals, sens_temps, 
            heat_demand, cool_demand, heat_cops, cool_cops, solar_gains
        )
        
        # Verify correct sensors were published
        expected_sensors = [
            'p_heat0',
            'p_cool0', 
            'p_deferrable0',  # Net power (backward compatibility)
            'temp_predicted0',
            'thermal_mode0',
            'heating_demand0',
            'cooling_demand0',
            'solar_gains0',
            'cop_heat0',
            'cop_cool0'
        ]
        
        # Extract sensor names from calls
        actual_sensors = [call.args[0] for call in mock_publish.call_args_list]
        
        # Verify all expected sensors were published
        for sensor in expected_sensors:
            assert sensor in actual_sensors
```

## 3. Edge Case Tests

### 3.1. Extreme Temperature Test

```python
def test_dual_mode_extreme_temperatures():
    """Test dual-mode behavior with extreme temperature scenarios."""
    # Create test configuration with narrow comfort band
    optim_conf = {
        "prediction_horizon": 6,
        "def_load_config": [
            {
                "thermal_battery": {
                    "dual_mode_enabled": True,
                    "heat_supply_temperature": 35.0,
                    "cool_supply_temperature": 12.0,
                    "heat_carnot_efficiency": 0.4,
                    "cool_carnot_efficiency": 0.45,
                    "volume": 20.0,
                    "start_temperature": 22.0,
                    "min_temperatures": [21.0] * 6,  # Narrow band
                    "max_temperatures": [23.0] * 6,  # Narrow band
                    "u_value": 0.5,
                    "envelope_area": 400.0,
                    "ventilation_rate": 0.5,
                    "heated_volume": 300.0
                }
            }
        ],
        "nominal_power_of_deferrable_loads": [5.0],
        "treat_deferrable_load_as_semi_cont": [True]
    }
    
    # Test data with extremely cold then extremely hot temperatures
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=6, freq='30min'),
        'load_power': [0.5] * 6,
        'pv_power': [0.0] * 6,
        'outdoor_temperature': [-10.0, -5.0, 0.0, 35.0, 40.0, 45.0]  # Extreme cold to extreme hot
    })
    
    # Run optimization
    optimizer = Optimization()
    optimizer.optim_conf = optim_conf
    result = optimizer.perform_optimization(test_data)
    
    # Verify successful optimization
    assert result['optim_status'] == 'optimal'
    
    # Verify temperature stays within bounds despite extreme conditions
    assert np.all(result['temp_predicted0'] <= 23.0)
    assert np.all(result['temp_predicted0'] >= 21.0)
    
    # Verify appropriate mode selection
    # Should use heating for first half, cooling for second half
    heat_active = result.get('heat_active0', np.zeros(6))
    cool_active = result.get('cool_active0', np.zeros(6))
    
    assert np.any(heat_active[:3] > 0)  # Heating in cold period
    assert np.any(cool_active[3:] > 0)  # Cooling in hot period
```

### 3.2. Anti-Cycling Protection Test

```python
def test_anti_cycling_protection():
    """Test that anti-cycling protection prevents rapid mode switching."""
    # Create test configuration with strong anti-cycling protection
    optim_conf = {
        "prediction_horizon": 12,
        "def_load_config": [
            {
                "thermal_battery": {
                    "dual_mode_enabled": True,
                    "heat_supply_temperature": 35.0,
                    "cool_supply_temperature": 12.0,
                    "heat_carnot_efficiency": 0.4,
                    "cool_carnot_efficiency": 0.45,
                    "volume": 20.0,
                    "start_temperature": 22.0,
                    "min_temperatures": [20.0] * 12,
                    "max_temperatures": [24.0] * 12,
                    "u_value": 0.5,
                    "envelope_area": 400.0,
                    "ventilation_rate": 0.5,
                    "heated_volume": 300.0,
                    "min_runtime": 3,           # Must run for at least 3 timesteps
                    "transition_cooldown": 2,   # Must wait 2 timesteps between modes
                    "max_mode_switches": 2     # Maximum 2 mode switches allowed
                }
            }
        ],
        "nominal_power_of_deferrable_loads": [3.0],
        "treat_deferrable_load_as_semi_cont": [True]
    }
    
    # Test data with oscillating temperatures around the comfort band
    # This would normally cause rapid switching without anti-cycling protection
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=12, freq='30min'),
        'load_power': [0.5] * 12,
        'pv_power': [0.0] * 12,
        'outdoor_temperature': [15.0, 25.0, 15.0, 25.0, 15.0, 25.0, 15.0, 25.0, 15.0, 25.0, 15.0, 25.0]
    })
    
    # Run optimization
    optimizer = Optimization()
    optimizer.optim_conf = optim_conf
    result = optimizer.perform_optimization(test_data)
    
    # Verify successful optimization
    assert result['optim_status'] == 'optimal'
    
    # Extract mode variables
    heat_active = result.get('heat_active0', np.zeros(12))
    cool_active = result.get('cool_active0', np.zeros(12))
    
    # Count mode switches
    heat_switches = np.sum(np.abs(np.diff(np.concatenate(([0], heat_active)))))
    cool_switches = np.sum(np.abs(np.diff(np.concatenate(([0], cool_active)))))
    total_switches = heat_switches + cool_switches
    
    # Verify anti-cycling constraints were enforced
    assert total_switches <= 2  # Maximum 2 switches allowed
    
    # Verify minimum runtime
    for i in range(len(heat_active)):
        if heat_active[i] > 0 and (i == 0 or heat_active[i-1] == 0):
            # Found start of heating period
            assert np.all(heat_active[i:min(i+3, len(heat_active))] > 0)
    
    for i in range(len(cool_active)):
        if cool_active[i] > 0 and (i == 0 or cool_active[i-1] == 0):
            # Found start of cooling period
            assert np.all(cool_active[i:min(i+3, len(cool_active))] > 0)
```

These test cases cover the core functionality, integration, and edge cases for the dual-mode thermal battery implementation.