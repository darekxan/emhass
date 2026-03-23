#!/usr/bin/env python

import unittest

import numpy as np
import pandas as pd

from emhass import utils


class TestUnifiedThermalBalance(unittest.TestCase):
    """Test cases for the unified thermal balance model."""

    def test_calculate_thermal_balance_basic(self):
        """Test basic functionality of the unified thermal balance calculation."""
        # Define common parameters
        u_value = 0.3
        envelope_area = 400.0
        ventilation_rate = 0.5
        heated_volume = 250.0
        optimization_time_step = 30

        # Test with mixed temperature conditions (both heating and cooling needed)
        indoor_target_temp = 22.0
        outdoor_temps = np.array([5.0, 15.0, 22.0, 30.0])  # Cold to hot

        # Calculate thermal balance
        balance = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temps,
            optimization_time_step=optimization_time_step,
        )

        # Check that the result includes all expected components
        self.assertIn("thermal_balance_kwh", balance)
        self.assertIn("thermal_load_kwh", balance)
        self.assertIn("solar_gains_kwh", balance)
        self.assertIn("internal_gains_kwh", balance)

        # Verify the thermal balance sign follows physical principles
        # When outdoor < indoor (5.0 < 22.0): Positive balance (heating needed)
        self.assertGreater(balance["thermal_balance_kwh"][0], 0.0)

        # When outdoor = indoor (22.0 = 22.0): Zero or near-zero balance (no heating/cooling)
        self.assertAlmostEqual(balance["thermal_balance_kwh"][2], 0.0, delta=0.01)

        # When outdoor > indoor (30.0 > 22.0): Negative balance (cooling needed)
        self.assertLess(balance["thermal_balance_kwh"][3], 0.0)

        # Monotonicity check: as outdoor temp increases, thermal_balance should decrease
        self.assertTrue(
            np.all(np.diff(balance["thermal_balance_kwh"]) <= 0),
            "Thermal balance should decrease monotonically as outdoor temperature increases",
        )

    def test_calculate_thermal_balance_with_solar(self):
        """Test thermal balance with solar gains."""
        # Define parameters
        u_value = 0.3
        envelope_area = 400.0
        ventilation_rate = 0.5
        heated_volume = 250.0
        indoor_target_temp = 22.0
        optimization_time_step = 30
        window_area = 50.0
        shgc = 0.6

        # Test temperatures and solar irradiance
        outdoor_temps = np.array([15.0, 15.0, 15.0, 15.0])  # Constant outdoor temp
        solar_irradiance = np.array([0.0, 200.0, 600.0, 1000.0])  # Increasing solar gain

        # Calculate thermal balance with no solar gains
        balance_no_solar = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temps,
            optimization_time_step=optimization_time_step,
        )

        # Calculate thermal balance with solar gains
        balance_with_solar = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temps,
            optimization_time_step=optimization_time_step,
            solar_irradiance_forecast=solar_irradiance,
            window_area=window_area,
            shgc=shgc,
        )

        # Verify that solar gains are correctly calculated
        self.assertTrue(np.all(balance_with_solar["solar_gains_kwh"] >= 0.0))
        self.assertTrue(np.all(np.diff(balance_with_solar["solar_gains_kwh"]) > 0))

        # For positive thermal balance (heating needed), solar gains should reduce demand
        # i.e., with_solar <= no_solar (equal at timestep 0 where solar_irradiance=0)
        constant_thermal_balance = balance_no_solar["thermal_balance_kwh"][0]

        # Verify solar gains always reduce or equal the thermal balance
        # (equal at zero-gain timestep, strictly less at non-zero timesteps)
        self.assertTrue(
            np.all(balance_with_solar["thermal_balance_kwh"] <= constant_thermal_balance),
            "Solar gains should reduce or maintain thermal balance (less heating or more cooling needed)",
        )

        # Verify that thermal balance decreases monotonically as solar gain increases
        self.assertTrue(
            np.all(np.diff(balance_with_solar["thermal_balance_kwh"]) < 0),
            "Thermal balance should decrease monotonically as solar irradiance increases",
        )

        # Verify with enough solar gain, heating demand can flip to cooling demand (sign change)
        # First timestep should be positive balance (heating needed at 15°C with no solar gain)
        self.assertGreater(balance_with_solar["thermal_balance_kwh"][0], 0.0)
        # Last timestep should be negative balance (cooling needed with 1000 W/m² solar gain)
        self.assertLess(balance_with_solar["thermal_balance_kwh"][3], 0.0)

    def test_calculate_thermal_balance_with_internal_gains(self):
        """Test thermal balance with internal gains."""
        # Define parameters
        u_value = 0.3
        envelope_area = 400.0
        ventilation_rate = 0.5
        heated_volume = 250.0
        indoor_target_temp = 22.0
        optimization_time_step = 30

        # Test temperatures and internal gains
        outdoor_temps = np.array([15.0, 15.0, 15.0, 15.0])  # Constant outdoor temp
        internal_gains = np.array([0.0, 1000.0, 3000.0, 5000.0])  # Increasing internal gains (W)
        internal_gains_factor = 0.8  # 80% of electrical load becomes heat

        # Calculate thermal balance with no internal gains
        balance_no_internal = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temps,
            optimization_time_step=optimization_time_step,
        )

        # Calculate thermal balance with internal gains
        balance_with_internal = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temps,
            optimization_time_step=optimization_time_step,
            internal_gains_forecast=internal_gains,
            internal_gains_factor=internal_gains_factor,
        )

        # Verify that internal gains are correctly calculated
        self.assertTrue(np.all(balance_with_internal["internal_gains_kwh"] >= 0.0))
        self.assertTrue(np.all(np.diff(balance_with_internal["internal_gains_kwh"]) > 0))

        # For positive thermal balance (heating needed), internal gains should reduce demand
        constant_thermal_balance = balance_no_internal["thermal_balance_kwh"][0]

        # Verify internal gains always reduce or equal the thermal balance
        # (equal at zero-gain timestep, strictly less at non-zero timesteps)
        self.assertTrue(
            np.all(balance_with_internal["thermal_balance_kwh"] <= constant_thermal_balance),
            "Internal gains should reduce or maintain thermal balance (less heating or more cooling needed)",
        )

        # Verify that thermal balance decreases monotonically as internal gains increase
        self.assertTrue(
            np.all(np.diff(balance_with_internal["thermal_balance_kwh"]) < 0),
            "Thermal balance should decrease monotonically as internal gains increase",
        )

        # Verify with enough internal gain, heating demand can flip to cooling demand (sign change)
        # First timestep should be positive balance (heating needed at 15°C with no internal gain)
        self.assertGreater(balance_with_internal["thermal_balance_kwh"][0], 0.0)
        # Last timestep should be negative balance (cooling needed with 5000W internal gain)
        self.assertLess(balance_with_internal["thermal_balance_kwh"][3], 0.0)

    def test_calculate_unified_cop_basic(self):
        """Test basic functionality of the unified COP calculation for heat pumps."""
        # Test parameters
        thermal_balance = np.array([2.0, 1.0, 0.0, -1.0, -2.0])  # kWh, mix of heating and cooling
        outdoor_temps = np.array([0.0, 10.0, 20.0, 30.0, 40.0])  # °C
        heat_supply_temp = 35.0  # °C
        cool_supply_temp = 12.0  # °C
        heat_carnot_eff = 0.4
        cool_carnot_eff = 0.45

        # Calculate unified COP
        cops = utils.calculate_unified_cop(
            thermal_balance=thermal_balance,
            outdoor_temperature=outdoor_temps,
            heat_supply_temperature=heat_supply_temp,
            cool_supply_temperature=cool_supply_temp,
            heat_carnot_efficiency=heat_carnot_eff,
            cool_carnot_efficiency=cool_carnot_eff,
        )

        # Check that the result is a numpy array of the expected length
        self.assertIsInstance(cops, np.ndarray)
        self.assertEqual(len(cops), len(thermal_balance))

        # Verify that all COP values are positive and finite
        self.assertTrue(np.all(cops > 0))
        self.assertTrue(np.all(np.isfinite(cops)))

        # Verify COP values are within expected bounds
        self.assertTrue(np.all(cops >= 1.0))  # Lower bound: direct electric heating
        self.assertTrue(np.all(cops <= 10.0))  # Upper bound: realistic maximum

        # Verify COP values are as expected for heating mode
        for i in range(2):  # First two elements are heating (positive thermal balance)
            expected_cop = (
                heat_carnot_eff
                * (heat_supply_temp + 273.15)
                / abs(heat_supply_temp - outdoor_temps[i])
            )
            expected_cop = min(max(expected_cop, 1.0), 8.0)  # Apply bounds
            self.assertAlmostEqual(cops[i], expected_cop, delta=0.1)

        # Verify COP values are as expected for cooling mode
        for i in range(3, 5):  # Last two elements are cooling (negative thermal balance)
            expected_cop = (
                cool_carnot_eff
                * (cool_supply_temp + 273.15)
                / abs(cool_supply_temp - outdoor_temps[i])
            )
            expected_cop = min(max(expected_cop, 1.0), 10.0)  # Apply bounds
            self.assertAlmostEqual(cops[i], expected_cop, delta=0.1)

        # Zero thermal balance should give COP of 1.0 (no energy needed)
        self.assertEqual(cops[2], 1.0)

    def test_calculate_unified_cop_physical_trends(self):
        """Test that unified COP follows physical trends for heat pumps."""
        # For constant outdoor temperature
        thermal_balance = np.array([3.0, 2.0, 1.0, 0.0, -1.0, -2.0, -3.0])
        outdoor_temp = np.full_like(thermal_balance, 10.0)

        cops = utils.calculate_unified_cop(
            thermal_balance=thermal_balance, outdoor_temperature=outdoor_temp
        )

        # Zero thermal balance should get COP of 1.0
        self.assertEqual(cops[3], 1.0)

        # COP should be constant for all heating loads at same outdoor temp
        self.assertTrue(np.allclose(cops[0], cops[1]))
        self.assertTrue(np.allclose(cops[1], cops[2]))

        # COP should be constant for all cooling loads at same outdoor temp
        self.assertTrue(np.allclose(cops[4], cops[5]))
        self.assertTrue(np.allclose(cops[5], cops[6]))

        # Test with varying outdoor temperature for heating
        # Use temps that stay far from the clipping bound (heat_supply=35°C, clip at 8.0)
        # All temps below ~21°C give unclipped COP with default settings
        thermal_balance_heat = np.full(5, 2.0)  # Constant positive (heating)
        outdoor_temps_heat = np.array([-10.0, 0.0, 5.0, 10.0, 15.0])  # Increasing outdoor temp

        cops_heat = utils.calculate_unified_cop(
            thermal_balance=thermal_balance_heat, outdoor_temperature=outdoor_temps_heat
        )

        # COP should increase as outdoor temperature increases (for heating mode)
        # (smaller temp difference → higher Carnot COP; all points within unclipped range)
        self.assertTrue(
            np.all(np.diff(cops_heat) > 0),
            "Heating COP should increase as outdoor temperature increases",
        )

        # Test with varying outdoor temperature for cooling
        thermal_balance_cool = np.full(5, -2.0)  # Constant negative (cooling)
        outdoor_temps_cool = np.array([25.0, 30.0, 35.0, 40.0, 45.0])  # Increasing outdoor temp

        cops_cool = utils.calculate_unified_cop(
            thermal_balance=thermal_balance_cool, outdoor_temperature=outdoor_temps_cool
        )

        # COP should decrease as outdoor temperature increases (for cooling mode)
        self.assertTrue(
            np.all(np.diff(cops_cool) < 0),
            "Cooling COP should decrease as outdoor temperature increases",
        )

    def test_calculate_unified_cop_with_pandas_series(self):
        """Test that unified COP works with pandas Series input."""
        thermal_balance = np.array([2.0, 1.0, -1.0, -2.0])
        outdoor_temps_array = np.array([0.0, 10.0, 30.0, 40.0])
        outdoor_temps_series = pd.Series(outdoor_temps_array)

        # Calculate with numpy array
        cops_array = utils.calculate_unified_cop(
            thermal_balance=thermal_balance, outdoor_temperature=outdoor_temps_array
        )

        # Calculate with pandas Series
        cops_series = utils.calculate_unified_cop(
            thermal_balance=thermal_balance, outdoor_temperature=outdoor_temps_series
        )

        # Results should be identical
        np.testing.assert_array_almost_equal(cops_array, cops_series)

    def test_calculate_unified_cop_shape_mismatch(self):
        """Test that shape mismatch between thermal_balance and outdoor_temperature raises error."""
        thermal_balance = np.array([2.0, 1.0, -1.0, -2.0])
        outdoor_temps = np.array([0.0, 10.0, 30.0, 40.0, 50.0])  # One extra value

        with self.assertRaises(ValueError):
            utils.calculate_unified_cop(
                thermal_balance=thermal_balance, outdoor_temperature=outdoor_temps
            )


if __name__ == "__main__":
    unittest.main()
