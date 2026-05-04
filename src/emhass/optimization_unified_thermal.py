"""
Optimization implementation for unified thermal model with signed thermal balance.
This module extends the core Optimization class with the new unified thermal model implementation.
"""

import cvxpy as cp
import numpy as np

from emhass import utils


def _add_unified_thermal_constraints(self, constraints, k, data_opt, p_load):
    """
    Handle constraints for unified thermal model loads.

    This function implements the new unified thermal balance approach where:
    - A single signed thermal balance variable represents both heating and cooling needs
    - Positive values indicate heating demand
    - Negative values indicate cooling demand
    - The appropriate COP is automatically applied based on the sign

    Args:
        constraints: List of constraints to append to
        k: Deferrable load index
        data_opt: DataFrame with optimization data
        p_load: Power load variable array

    Returns:
        Tuple of (predicted_temp, thermal_balance, thermal_balance_var)
    """
    # Define thermal power variable (signed: positive = heating, negative = cooling)
    required_len = self.num_timesteps
    thermal_power_var = cp.Variable(required_len, name=f"thermal_power_{k}")

    # Extract configuration
    def_load_config = self.optim_conf["def_load_config"][k]
    config = def_load_config["thermal_config"]

    # Get basic parameters
    thermal_efficiency = config.get("thermal_efficiency", 5.0)
    heat_loss_coefficient = config.get("heat_loss_coefficient", 0.1)
    thermal_inertia = config.get("thermal_inertia", 0.0)
    start_temperature = config.get("start_temperature", 20.0)

    # Get capacity limits
    max_heating_capacity = config.get("max_heating_capacity", 5000) / 1000.0  # kW
    max_cooling_capacity = config.get("max_cooling_capacity", 4000) / 1000.0  # kW

    # Get COP parameters
    heat_params = config.get("heat_cop_params", {})
    cool_params = config.get("cool_cop_params", {})
    heat_supply_temp = heat_params.get("supply_temperature", 35.0)
    cool_supply_temp = cool_params.get("supply_temperature", 12.0)
    heat_carnot_eff = heat_params.get("carnot_efficiency", 0.4)
    cool_carnot_eff = cool_params.get("carnot_efficiency", 0.45)

    # Get building physics parameters for thermal balance calculation
    u_value = config.get("u_value", 0.5)
    envelope_area = config.get("envelope_area", 350.0)
    ventilation_rate = config.get("ventilation_rate", 0.5)
    heated_volume = config.get("heated_volume", 250.0)

    # Get comfort parameters (target or min/max)
    target_temp = config.get("target_temperature")
    min_temperatures = config.get("min_temperatures", [])
    max_temperatures = config.get("max_temperatures", [])

    # Get window parameters for solar gain
    window_area = config.get("window_area")
    shgc = config.get("shgc", 0.6)
    internal_gains_factor = config.get("internal_gains_factor", 0.0)

    # Get clean outdoor temperature and initialize parameters
    outdoor_temp_arr = self._get_clean_outdoor_temp(data_opt, required_len)

    # If we're using parameter-based optimization, set up the parameters
    if k in self.param_thermal:
        params = self.param_thermal[k]

        # Update outdoor temperature parameter
        params["outdoor_temp"].value = outdoor_temp_arr

        # Calculate thermal balance components
        # This includes thermal load, solar gains, internal gains
        indoor_target_temp = target_temp
        if isinstance(target_temp, list):
            indoor_target_temp = target_temp[0]
        elif target_temp is None and min_temperatures and max_temperatures:
            # Use average of min/max as target for thermal balance calculation
            indoor_target_temp = (min_temperatures[0] + max_temperatures[0]) / 2

        # Get solar irradiance if available
        solar_irradiance = None
        if "ghi" in data_opt.columns and window_area is not None:
            vals = data_opt["ghi"].values
            if len(vals) < required_len:
                vals = np.concatenate((vals, np.zeros(required_len - len(vals))))
            solar_irradiance = vals[:required_len]

        # Get internal gains if available
        internal_gains = None
        if internal_gains_factor > 0:
            internal_gains = p_load

        # Calculate unified thermal balance using our new function
        thermal_balance = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temp_arr,
            optimization_time_step=int(self.freq.total_seconds() / 60),
            solar_irradiance_forecast=solar_irradiance,
            window_area=window_area,
            shgc=shgc,
            internal_gains_forecast=internal_gains,
            internal_gains_factor=internal_gains_factor,
        )

        # Set parameter values
        params["thermal_balance"].value = thermal_balance["thermal_balance_kwh"]
        params["solar_gains"].value = thermal_balance["solar_gains_kwh"]

        # Calculate unified COP based on thermal balance sign
        unified_cop = utils.calculate_unified_cop(
            thermal_balance=thermal_balance["thermal_balance_kwh"],
            outdoor_temperature=outdoor_temp_arr,
            heat_supply_temperature=heat_supply_temp,
            cool_supply_temperature=cool_supply_temp,
            heat_carnot_efficiency=heat_carnot_eff,
            cool_carnot_efficiency=cool_carnot_eff,
        )
        params["unified_cop"].value = unified_cop
    else:
        # Create parameters for the first time
        self.param_thermal[k] = {}
        params = self.param_thermal[k]

        # Create parameters
        params["outdoor_temp"] = cp.Parameter(required_len, name=f"thermal_outdoor_temp_{k}")
        params["start_temp"] = cp.Parameter(name=f"thermal_start_temp_{k}")
        params["thermal_balance"] = cp.Parameter(required_len, name=f"thermal_balance_{k}")
        params["solar_gains"] = cp.Parameter(required_len, name=f"solar_gains_{k}")
        params["unified_cop"] = cp.Parameter(required_len, name=f"unified_cop_{k}")

        # Create min/max temperature parameters if needed
        if min_temperatures:
            params["min_temps"] = cp.Parameter(required_len, name=f"thermal_min_temps_{k}")
            params["min_temps"].value = _extend_to_length(min_temperatures, required_len)

        if max_temperatures:
            params["max_temps"] = cp.Parameter(required_len, name=f"thermal_max_temps_{k}")
            params["max_temps"].value = _extend_to_length(max_temperatures, required_len)

        # Set parameter values
        params["start_temp"].value = start_temperature
        params["outdoor_temp"].value = outdoor_temp_arr

        # Calculate thermal balance components
        indoor_target_temp = target_temp
        if isinstance(target_temp, list):
            indoor_target_temp = target_temp[0]
        elif target_temp is None and min_temperatures and max_temperatures:
            indoor_target_temp = (min_temperatures[0] + max_temperatures[0]) / 2

        # Get solar irradiance if available
        solar_irradiance = None
        if "ghi" in data_opt.columns and window_area is not None:
            vals = data_opt["ghi"].values
            if len(vals) < required_len:
                vals = np.concatenate((vals, np.zeros(required_len - len(vals))))
            solar_irradiance = vals[:required_len]

        # Get internal gains if available
        internal_gains = None
        if internal_gains_factor > 0:
            internal_gains = p_load

        # Calculate unified thermal balance
        thermal_balance = utils.calculate_thermal_balance(
            u_value=u_value,
            envelope_area=envelope_area,
            ventilation_rate=ventilation_rate,
            heated_volume=heated_volume,
            indoor_target_temperature=indoor_target_temp,
            outdoor_temperature_forecast=outdoor_temp_arr,
            optimization_time_step=int(self.freq.total_seconds() / 60),
            solar_irradiance_forecast=solar_irradiance,
            window_area=window_area,
            shgc=shgc,
            internal_gains_forecast=internal_gains,
            internal_gains_factor=internal_gains_factor,
        )

        # Set parameter values
        params["thermal_balance"].value = thermal_balance["thermal_balance_kwh"]
        params["solar_gains"].value = thermal_balance["solar_gains_kwh"]

        # Calculate unified COP based on thermal balance sign
        unified_cop = utils.calculate_unified_cop(
            thermal_balance=thermal_balance["thermal_balance_kwh"],
            outdoor_temperature=outdoor_temp_arr,
            heat_supply_temperature=heat_supply_temp,
            cool_supply_temperature=cool_supply_temp,
            heat_carnot_efficiency=heat_carnot_eff,
            cool_carnot_efficiency=cool_carnot_eff,
        )
        params["unified_cop"].value = unified_cop

    # Define temperature variable
    predicted_temp = cp.Variable(required_len, name=f"temp_load_{k}")

    # Set initial temperature
    constraints.append(predicted_temp[0] == params["start_temp"])

    # Thermal dynamics - define mode indicators
    is_heating = cp.Variable(required_len, boolean=True, name=f"is_heating_{k}")

    # Bound thermal power based on capacity limits
    constraints.append(thermal_power_var <= max_heating_capacity * is_heating)
    constraints.append(thermal_power_var >= -max_cooling_capacity * (1 - is_heating))

    # Add thermal inertia handling
    L = int(thermal_inertia / self.time_step)

    # Set up temperature dynamics equation
    # T[t+1] = T[t] + thermal_efficiency * power[t] - heat_loss * (T[t] - T_outdoor[t])
    # Main dynamics (with inertia if L > 0)
    if L > 0:
        # Temperature update with delayed power effect (inertia)
        constraints.append(
            predicted_temp[1 + L :]
            == predicted_temp[L:-1]
            + (thermal_efficiency * thermal_power_var[: -1 - L])
            - (heat_loss_coefficient * (predicted_temp[L:-1] - params["outdoor_temp"][L:-1]))
        )

        # Startup "dead zone" dynamics (when thermal effect hasn't kicked in yet)
        constraints.append(
            predicted_temp[1 : 1 + L]
            == predicted_temp[:L]
            - (heat_loss_coefficient * (predicted_temp[:L] - params["outdoor_temp"][:L]))
        )
    else:
        # Temperature update with immediate power effect (no inertia)
        constraints.append(
            predicted_temp[1:]
            == predicted_temp[:-1]
            + (thermal_efficiency * thermal_power_var[:-1])
            - (heat_loss_coefficient * (predicted_temp[:-1] - params["outdoor_temp"][:-1]))
        )

    # Temperature comfort constraints (min/max)
    if "min_temps" in params:
        constraints.append(predicted_temp >= params["min_temps"])

    if "max_temps" in params:
        constraints.append(predicted_temp <= params["max_temps"])

    # Target temperature constraint if specified
    if target_temp is not None:
        if isinstance(target_temp, list):
            target_temp_arr = _extend_to_length(target_temp, required_len)
            # Use soft constraints with penalty
            target_deviation = cp.Variable(required_len, nonneg=True, name=f"temp_dev_{k}")
            constraints.append(predicted_temp - target_temp_arr <= target_deviation)
            constraints.append(target_temp_arr - predicted_temp <= target_deviation)
            penalty_weight = config.get("target_penalty_weight", 10.0)
            self.model.setObjective(
                self.model.getObjective() - penalty_weight * cp.sum(target_deviation)
            )
        else:
            # Single target temperature
            target_deviation = cp.Variable(required_len, nonneg=True, name=f"temp_dev_{k}")
            constraints.append(predicted_temp - target_temp <= target_deviation)
            constraints.append(target_temp - predicted_temp <= target_deviation)
            penalty_weight = config.get("target_penalty_weight", 10.0)
            self.model.setObjective(
                self.model.getObjective() - penalty_weight * cp.sum(target_deviation)
            )

    # Connect thermal power to the actual electrical power consumption
    # Electrical power = thermal power / COP (absolute value with appropriate COP)

    # We need to create positive and negative parts for thermal power
    therm_pos = cp.Variable(required_len, nonneg=True, name=f"thermal_pos_{k}")
    therm_neg = cp.Variable(required_len, nonneg=True, name=f"thermal_neg_{k}")

    # Decompose thermal power into positive and negative parts
    constraints.append(thermal_power_var == therm_pos - therm_neg)

    # Constraints to ensure correct mode is selected
    constraints.append(therm_pos <= max_heating_capacity * is_heating)
    constraints.append(therm_neg <= max_cooling_capacity * (1 - is_heating))

    # Electrical power calculation with unified COP
    # p_load[k] = therm_pos / unified_cop + therm_neg / unified_cop
    constraints.append(p_load[k] == (therm_pos + therm_neg) / params["unified_cop"])

    # Return predicted temperature and thermal balance
    return predicted_temp, params["thermal_balance"], thermal_power_var


def _extend_to_length(values, length):
    """Helper function to extend a list or value to the required length."""
    if isinstance(values, list):
        if len(values) >= length:
            return np.array(values[:length])
        else:
            # Extend by repeating the last value
            extended = values.copy()
            last_val = extended[-1] if extended else None
            extended.extend([last_val] * (length - len(extended)))
            return np.array(extended)
    else:
        # Single value, create array of that value
        return np.full(length, values)
