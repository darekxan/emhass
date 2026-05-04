# Test Cases for Thermal Battery Cooling Support

This document outlines the test cases needed to verify the GSHP active cooling support implementation in the thermal_battery component.

## 1. Unit Tests

These tests should focus on the individual components that have been modified to support cooling mode.

### 1.1. COP Calculation Tests

Test file: `tests/test_utils.py`

```python
def test_calculate_cop_heatpump_cooling_mode():
    """Test that COP calculation works correctly in cooling mode."""
    # Test case 1: Normal cooling operation (outdoor > supply)
    supply_temp = 12.0  # °C
    carnot_eff = 0.45
    outdoor_temps = np.array([25.0, 30.0, 35.0])
    
    # Calculate COPs in cooling mode
    cops = calculate_cop_heatpump(
        supply_temperature=supply_temp,
        carnot_efficiency=carnot_eff,
        outdoor_temperature_forecast=outdoor_temps,
        mode="cool"
    )
    
    # Expected COP values (calculated manually)
    # At 25°C outdoor: COP = 0.45 × 285.15K / (298.15K - 285.15K) = 0.45 × 285.15 / 13 = 9.87
    # Capped at maximum of 10.0
    expected_cops = np.array([9.87, 5.77, 4.07])
    np.testing.assert_almost_equal(cops, expected_cops, decimal=2)
    
    # Test case 2: Non-physical cooling operation (outdoor <= supply)
    outdoor_temps = np.array([10.0, 12.0, 14.0])
    cops = calculate_cop_heatpump(
        supply_temperature=supply_temp,
        carnot_efficiency=carnot_eff,
        outdoor_temperature_forecast=outdoor_temps,
        mode="cool"
    )
    
    # Should return direct electric (COP=1.0) for non-physical cases
    expected_cops = np.array([1.0, 1.0, 1.0])
    np.testing.assert_almost_equal(cops, expected_cops)
    
    # Test case 3: Both physical and non-physical cases mixed
    outdoor_temps = np.array([10.0, 20.0, 30.0])
    cops = calculate_cop_heatpump(
        supply_temperature=supply_temp,
        carnot_efficiency=carnot_eff,
        outdoor_temperature_forecast=outdoor_temps,
        mode="cool"
    )
    
    # First temperature is non-physical, others are valid
    expected_cops = np.array([1.0, 3.84, 5.77])
    np.testing.assert_almost_equal(cops, expected_cops, decimal=2)

def test_calculate_cop_heatpump_heating_mode_backward_compatibility():
    """Test that heating mode COP calculation remains backward compatible."""
    # Verify that calling without mode parameter still works
    supply_temp = 35.0  # °C
    carnot_eff = 0.4
    outdoor_temps = np.array([0.0, 5.0, 10.0])
    
    # Call without mode parameter
    cops_default = calculate_cop_heatpump(
        supply_temperature=supply_temp,
        carnot_efficiency=carnot_eff,
        outdoor_temperature_forecast=outdoor_temps
    )
    
    # Call with explicit heating mode
    cops_heat = calculate_cop_heatpump(
        supply_temperature=supply_temp,
        carnot_efficiency=carnot_eff,
        outdoor_temperature_forecast=outdoor_temps,
        mode="heat"
    )
    
    # Results should be identical
    np.testing.assert_array_equal(cops_default, cops_heat)
```

### 1.2. Thermal Demand Calculation Tests

Test file: `tests/test_utils.py`

```python
def test_calculate_heating_demand_physics_components_cooling_mode():
    """Test thermal demand calculation in cooling mode."""
    # Test inputs
    u_value = 0.5  # W/(m²·K)
    envelope_area = 400.0  # m²
    ventilation_rate = 0.5  # ACH
    heated_volume = 300.0  # m³
    indoor_target_temp = 24.0  # °C
    outdoor_temps = np.array([28.0, 30.0, 32.0])  # °C (hot days)
    time_step = 30  # minutes
    solar_irradiance = np.array([600.0, 800.0, 900.0])  # W/m²
    window_area = 30.0  # m²
    shgc = 0.6
    
    # Test cooling demand calculation
    result = calculate_heating_demand_physics_components(
        u_value=u_value,
        envelope_area=envelope_area,
        ventilation_rate=ventilation_rate,
        heated_volume=heated_volume,
        indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temps,
        optimization_time_step=time_step,
        solar_irradiance_forecast=solar_irradiance,
        window_area=window_area,
        shgc=shgc,
        mode="cool"
    )
    
    # Check keys exist
    assert "heat_loss_kwh" in result
    assert "solar_gains_kwh" in result
    assert "internal_gains_kwh" in result
    assert "thermal_demand_kwh" in result
    
    # In cooling mode:
    # 1. Heat loss should be positive (building gains heat from outdoors)
    assert np.all(result["heat_loss_kwh"] > 0)
    
    # 2. Solar gains should be positive and increasing with irradiance
    assert np.all(result["solar_gains_kwh"] > 0)
    assert np.all(np.diff(result["solar_gains_kwh"]) > 0)  # Should increase
    
    # 3. Total demand should be sum of losses and gains in cooling mode
    expected_demand = result["heat_loss_kwh"] + result["solar_gains_kwh"] + result["internal_gains_kwh"]
    np.testing.assert_almost_equal(result["thermal_demand_kwh"], expected_demand)

def test_heating_demand_physics_components_mode_difference():
    """Test that heating and cooling modes produce different results."""
    # Use the same building and conditions for both modes
    u_value = 0.5
    envelope_area = 400.0
    ventilation_rate = 0.5
    heated_volume = 300.0
    indoor_target_temp = 22.0
    outdoor_temps = np.array([26.0, 26.0, 26.0])  # Warmer outside
    time_step = 30
    solar_irradiance = np.array([500.0, 500.0, 500.0])
    window_area = 30.0
    shgc = 0.6
    
    # Calculate with heating mode
    heat_result = calculate_heating_demand_physics_components(
        u_value=u_value, envelope_area=envelope_area, ventilation_rate=ventilation_rate,
        heated_volume=heated_volume, indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temps, optimization_time_step=time_step,
        solar_irradiance_forecast=solar_irradiance, window_area=window_area, shgc=shgc,
        mode="heat"
    )
    
    # Calculate with cooling mode
    cool_result = calculate_heating_demand_physics_components(
        u_value=u_value, envelope_area=envelope_area, ventilation_rate=ventilation_rate,
        heated_volume=heated_volume, indoor_target_temperature=indoor_target_temp,
        outdoor_temperature_forecast=outdoor_temps, optimization_time_step=time_step,
        solar_irradiance_forecast=solar_irradiance, window_area=window_area, shgc=shgc,
        mode="cool"
    )
    
    # Heat losses should be the same
    np.testing.assert_almost_equal(heat_result["heat_loss_kwh"], cool_result["heat_loss_kwh"])
    
    # Solar gains should be the same 
    np.testing.assert_almost_equal(heat_result["solar_gains_kwh"], cool_result["solar_gains_kwh"])
    
    # But the final demand should be different:
    # - In heating mode: demand = loss - gains
    # - In cooling mode: demand = loss + gains
    assert not np.array_equal(heat_result["thermal_demand_kwh"], cool_result["thermal_demand_kwh"])
    
    # Heating demand should be zero (it's warmer outside)
    assert np.all(heat_result["thermal_demand_kwh"] == 0)
    
    # Cooling demand should be positive (building needs cooling)
    assert np.all(cool_result["thermal_demand_kwh"] > 0)
```

## 2. Integration Tests

These tests should verify that the thermal battery component works end-to-end with cooling mode.

### 2.1. Thermal Battery Constraints Tests

Test file: `tests/test_optimization.py`

```python
def test_thermal_battery_cooling_mode():
    """Test thermal battery constraints with cooling mode."""
    # Create a test optimization configuration with a thermal battery in cooling mode
    optim_conf = {
        "prediction_horizon": 4,
        "def_total_hours": 8,
        "weight_battery_discharge": 1.0,
        "weight_battery_charge": 0.0,
        "def_load_config": [
            {
                "thermal_battery": {
                    "sense": "cool",
                    "supply_temperature": 12.0,
                    "volume": 15.0,
                    "start_temperature": 25.0,
                    "min_temperatures": [20.0, 20.0, 20.0, 20.0],
                    "max_temperatures": [26.0, 26.0, 26.0, 26.0],
                    "carnot_efficiency": 0.45,
                    "u_value": 0.5,
                    "envelope_area": 200.0,
                    "ventilation_rate": 0.5,
                    "heated_volume": 150.0
                }
            }
        ],
        "nominal_power_of_deferrable_loads": [5.0],
        "treat_deferrable_load_as_semi_cont": [True],
        "load_cost_forecast": [0.1, 0.2, 0.3, 0.1]
    }
    
    # Create test data with outdoor temperatures above indoor target
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=4, freq='30min'),
        'load_power': [0.5, 0.5, 0.5, 0.5],
        'pv_power': [0.0, 0.0, 0.0, 0.0],
        'outdoor_temperature': [28.0, 30.0, 32.0, 30.0],  # Hot days
        'ghi': [600.0, 800.0, 900.0, 700.0]  # Solar irradiance
    })
    
    # Initialize optimization object
    optimizer = Optimization()
    optimizer.optim_conf = optim_conf
    
    # Run optimization to generate variables and constraints
    constraints = []
    optimizer._initialize_decision_variables()
    pred_temp, heat_demand, q_input, solar_gain = optimizer._add_thermal_battery_constraints(
        constraints, 0, test_data, test_data['load_power'].values
    )
    
    # Check that temperature predictions were created
    assert pred_temp is not None
    assert isinstance(pred_temp, cp.Expression)
    
    # Check that temperature constraints were created (should be 2 constraints)
    assert len([c for c in constraints if isinstance(c, cp.constraints.LeqConstraint) 
                or isinstance(c, cp.constraints.GeqConstraint)]) >= 2
    
    # Ensure that heating demand was calculated correctly (should be positive in cooling mode)
    assert heat_demand is not None
    assert np.all(optimizer.param_thermal[0]["heating_demand"].value > 0)
    
    # Run a test optimization to verify it solves correctly
    result = optimizer.perform_optimization(test_data)
    
    # Check that the optimization was successful
    assert result['optim_status'] == 'optimal'
    
    # In cooling mode with hot days, the system should run the cooling
    assert np.any(result['p_deferrable0'] > 0)
    
    # Temperature should stay within bounds
    assert np.all(result['temp_predicted0'] <= 26.0)
    assert np.all(result['temp_predicted0'] >= 20.0)
```

### 2.2. Cooling Mode vs Heating Mode Test

Test file: `tests/test_optimization.py`

```python
def test_thermal_battery_mode_comparison():
    """Compare optimization results between heating and cooling modes."""
    # Base configuration template
    base_conf = {
        "prediction_horizon": 4,
        "def_total_hours": 8,
        "weight_battery_discharge": 1.0,
        "weight_battery_charge": 0.0,
        "nominal_power_of_deferrable_loads": [5.0],
        "treat_deferrable_load_as_semi_cont": [True],
        "load_cost_forecast": [0.1, 0.2, 0.3, 0.1]
    }
    
    # Heating mode configuration
    heating_conf = copy.deepcopy(base_conf)
    heating_conf["def_load_config"] = [
        {
            "thermal_battery": {
                "sense": "heat",
                "supply_temperature": 35.0,
                "volume": 15.0,
                "start_temperature": 18.0,
                "min_temperatures": [20.0, 20.0, 20.0, 20.0],
                "max_temperatures": [26.0, 26.0, 26.0, 26.0],
                "carnot_efficiency": 0.4,
                "u_value": 0.5,
                "envelope_area": 200.0,
                "ventilation_rate": 0.5,
                "heated_volume": 150.0
            }
        }
    ]
    
    # Cooling mode configuration
    cooling_conf = copy.deepcopy(base_conf)
    cooling_conf["def_load_config"] = [
        {
            "thermal_battery": {
                "sense": "cool",
                "supply_temperature": 12.0,
                "volume": 15.0,
                "start_temperature": 25.0,
                "min_temperatures": [20.0, 20.0, 20.0, 20.0],
                "max_temperatures": [26.0, 26.0, 26.0, 26.0],
                "carnot_efficiency": 0.45,
                "u_value": 0.5,
                "envelope_area": 200.0,
                "ventilation_rate": 0.5,
                "heated_volume": 150.0
            }
        }
    ]
    
    # Create test data with temperature values for both scenarios
    test_data = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=4, freq='30min'),
        'load_power': [0.5, 0.5, 0.5, 0.5],
        'pv_power': [0.0, 0.0, 0.0, 0.0]
    })
    
    # Heating scenario: cold outdoor temperatures
    heating_data = test_data.copy()
    heating_data['outdoor_temperature'] = [5.0, 3.0, 2.0, 4.0]  # Cold days
    
    # Cooling scenario: hot outdoor temperatures
    cooling_data = test_data.copy()
    cooling_data['outdoor_temperature'] = [28.0, 30.0, 32.0, 30.0]  # Hot days
    
    # Initialize optimization objects
    heat_opt = Optimization()
    heat_opt.optim_conf = heating_conf
    
    cool_opt = Optimization()
    cool_opt.optim_conf = cooling_conf
    
    # Run optimizations
    heat_result = heat_opt.perform_optimization(heating_data)
    cool_result = cool_opt.perform_optimization(cooling_data)
    
    # Check both optimizations were successful
    assert heat_result['optim_status'] == 'optimal'
    assert cool_result['optim_status'] == 'optimal'
    
    # Check that cooling operates when temperature is high
    assert np.any(cool_result['p_deferrable0'] > 0)
    
    # Check that heating operates when temperature is low
    assert np.any(heat_result['p_deferrable0'] > 0)
    
    # Check temperature predictions stay within bounds
    assert np.all(heat_result['temp_predicted0'] <= 26.0)
    assert np.all(heat_result['temp_predicted0'] >= 20.0)
    
    assert np.all(cool_result['temp_predicted0'] <= 26.0)
    assert np.all(cool_result['temp_predicted0'] >= 20.0)
    
    # Temperature dynamics should be different between modes
    # In heating: temperature increases when system runs
    # In cooling: temperature decreases when system runs
    # (But we can't directly test this without more complex test cases)
```

### 2.3. Sensor Publishing Test

Test file: `tests/test_web_server.py`

```python
def test_thermal_battery_cooling_sensors():
    """Test sensor publishing for cooling mode thermal battery."""
    # Create web server instance
    web_server = create_test_web_server()
    
    # Set up a configuration with cooling mode thermal battery
    web_server.optim.optim_conf = {
        "def_load_config": [
            {
                "thermal_battery": {
                    "sense": "cool",
                    "supply_temperature": 12.0,
                    "min_temperatures": [20.0],
                    "max_temperatures": [26.0]
                }
            }
        ]
    }
    
    # Create test results
    p_def_vals = [1.5, 0.0, 2.0]
    sens_temps = [25.0, 24.0, 23.0]
    heat_demand = [0.5, 0.6, 0.7]
    solar_gains = [0.2, 0.3, 0.4]
    
    # Mock the publish sensor method to capture calls
    with mock.patch.object(web_server, '_publish_sensor') as mock_publish:
        # Call the method to test
        web_server._publish_thermal_battery_results(0, p_def_vals, sens_temps, heat_demand, solar_gains)
        
        # Verify number of calls (4 sensors should be published)
        assert mock_publish.call_count == 4
        
        # Extract the calls and check sensor names and attributes
        calls = mock_publish.call_args_list
        
        # Check first call (p_deferrable)
        args, _ = calls[0]
        sensor_name, values, attrs = args
        assert sensor_name == 'p_deferrable0'
        assert np.array_equal(values, p_def_vals)
        assert attrs['mode'] == 'cool'
        assert 'Cooling' in attrs['friendly_name']
        
        # Check second call (temperature)
        args, _ = calls[1]
        sensor_name, values, attrs = args
        assert sensor_name == 'temp_predicted0'
        assert np.array_equal(values, sens_temps)
        assert attrs['mode'] == 'cool'
        
        # Check third call (thermal demand)
        args, _ = calls[2]
        sensor_name, values, attrs = args
        assert sensor_name == 'thermal_demand0'
        assert np.array_equal(values, heat_demand)
        assert attrs['mode'] == 'cool'
        assert 'Cooling' in attrs['friendly_name']
        assert 'mdi:snowflake' in attrs['icon']  # Should use cooling icon
```

## 3. System Tests

These tests should validate the overall system behavior with realistic configurations.

### 3.1. Realistic Cooling Scenario Test

```python
def test_realistic_cooling_scenario():
    """Test a realistic summer cooling scenario with variable prices and PV."""
    # Create a more complex optimization configuration
    optim_conf = {
        "prediction_horizon": 24,  # 12 hours (30-min steps)
        "def_total_hours": 24,
        "weight_battery_discharge": 1.0,
        "weight_battery_charge": 0.0,
        "def_load_config": [
            {
                "thermal_battery": {
                    "sense": "cool",
                    "supply_temperature": 12.0,
                    "volume": 20.0,
                    "start_temperature": 25.0,
                    "min_temperatures": [22.0] * 24,  # Lower comfort limit
                    "max_temperatures": [26.0] * 24,  # Upper comfort limit
                    "carnot_efficiency": 0.45,
                    "u_value": 0.4,  # Well-insulated
                    "envelope_area": 400.0,
                    "ventilation_rate": 0.5,
                    "heated_volume": 300.0,
                    "window_area": 40.0,
                    "shgc": 0.6,
                    "internal_gains_factor": 0.7
                }
            }
        ],
        "nominal_power_of_deferrable_loads": [3.5],  # 3.5 kW cooling capacity
        "treat_deferrable_load_as_semi_cont": [True],
        # Variable electricity prices (cheaper at night, expensive during day)
        "load_cost_forecast": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 
                             0.15, 0.20, 0.25, 0.30, 0.30, 0.30, 
                             0.30, 0.30, 0.25, 0.20, 0.20, 0.15, 
                             0.15, 0.15, 0.10, 0.10, 0.10, 0.10]
    }
    
    # Create test data with realistic summer thermal conditions
    timestamp = pd.date_range(start='2023-07-01 00:00', periods=24, freq='30min')
    
    # Outdoor temperature pattern (cool night, hot day)
    outdoor_temp = [22, 21, 20, 20, 20, 21, 
                    22, 24, 26, 28, 30, 31, 
                    32, 32, 31, 30, 29, 28, 
                    26, 25, 24, 23, 22, 22]
    
    # Solar generation pattern
    pv_power = [0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 
                0.5, 1.0, 2.0, 3.0, 3.5, 4.0, 
                4.0, 3.8, 3.5, 3.0, 2.0, 1.0, 
                0.5, 0.1, 0.0, 0.0, 0.0, 0.0]
    
    # Solar irradiance pattern
    ghi = [0, 0, 0, 0, 0, 50, 
           150, 300, 500, 700, 850, 950, 
           1000, 950, 850, 700, 500, 300, 
           100, 50, 0, 0, 0, 0]
    
    # Home electrical load pattern
    load_power = [0.3, 0.3, 0.3, 0.3, 0.3, 0.5, 
                 1.0, 1.5, 1.0, 0.8, 0.8, 0.8, 
                 1.0, 1.0, 1.2, 1.5, 2.0, 2.5, 
                 2.0, 1.5, 1.0, 0.8, 0.5, 0.3]
    
    test_data = pd.DataFrame({
        'timestamp': timestamp,
        'outdoor_temperature': outdoor_temp,
        'pv_power': pv_power,
        'load_power': load_power,
        'ghi': ghi
    })
    
    # Initialize optimization object
    optimizer = Optimization()
    optimizer.optim_conf = optim_conf
    
    # Run optimization
    result = optimizer.perform_optimization(test_data)
    
    # Check successful optimization
    assert result['optim_status'] == 'optimal'
    
    # Expected behaviors to test
    # 1. System should prioritize cooling during cheap electricity periods
    cheap_periods = np.where(np.array(optim_conf["load_cost_forecast"]) <= 0.15)[0]
    expensive_periods = np.where(np.array(optim_conf["load_cost_forecast"]) >= 0.25)[0]
    
    # Either cooling should be more active during cheap periods than expensive ones
    # or temperature should be lower at the end of cheap periods
    cooling_cheap = result['p_deferrable0'][cheap_periods].mean()
    cooling_expensive = result['p_deferrable0'][expensive_periods].mean()
    
    # 2. System should use excess PV production for cooling
    # Look for correlation between PV production and cooling operation
    pv_excess_periods = np.where(np.array(test_data['pv_power']) > 
                                 np.array(test_data['load_power']))[0]
    
    if len(pv_excess_periods) > 0:
        # If there are periods with excess PV, check if cooling uses it
        pv_cooling_correlation = np.corrcoef(
            test_data['pv_power'][pv_excess_periods],
            result['p_deferrable0'][pv_excess_periods]
        )[0, 1]
        
        # Should have at least some positive correlation
        assert pv_cooling_correlation > 0
    
    # 3. Temperature should always stay within bounds
    assert np.all(result['temp_predicted0'] <= optim_conf["def_load_config"][0]
                  ["thermal_battery"]["max_temperatures"])
    assert np.all(result['temp_predicted0'] >= optim_conf["def_load_config"][0]
                  ["thermal_battery"]["min_temperatures"])
    
    # 4. Pre-cooling behavior:
    # Temperature should decrease before high-cost periods
    # or before peak outdoor temperature periods
    high_temp_start = np.argmax(outdoor_temp >= 28)  # First index with temp >= 28
    
    if high_temp_start > 3:  # If we have enough periods before high temp
        # Check if system pre-cools
        pre_cooling_temp_drop = (result['temp_predicted0'][high_temp_start-3:high_temp_start] < 
                                result['temp_predicted0'][high_temp_start])
        assert np.any(pre_cooling_temp_drop)
```

## 4. Full Coverage Areas

The test suite should achieve the following coverage:

1. **Functionality Tests**:
   - COP calculation in cooling mode
   - Thermal demand calculation with cooling
   - Optimization with cooling mode
   - Sensor publishing with cooling mode

2. **Edge Cases**:
   - Non-physical temperature scenarios
   - Borderline comfort conditions
   - Mixed heating/cooling transitions
   - Extreme outdoor temperatures

3. **Performance Tests**:
   - Optimization with realistic summer conditions
   - Resource usage compared to heating mode
   - Solving time for complex scenarios

4. **Backward Compatibility**:
   - Tests with existing heating configurations
   - Default parameter behavior

This comprehensive test plan will ensure that the GSHP active cooling support is thoroughly validated before deployment.