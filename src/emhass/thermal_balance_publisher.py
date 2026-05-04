"""
Thermal balance publisher module for unified thermal model.

This module implements the sensor publishing functionality for the unified thermal balance approach.
"""

import logging
from typing import Any

import pandas as pd

from emhass.retrieve_hass import RetrieveHass


async def publish_unified_thermal_data(
    rh: RetrieveHass,
    opt_res_latest: pd.DataFrame,
    idx: list[str],
    params: dict[str, Any],
    optim_conf: dict[str, Any],
    logger: logging.Logger,
    **common_kwargs,
) -> list[str]:
    """
    Publish thermal data using the unified thermal balance approach.

    Args:
        rh: RetrieveHass instance for publishing data
        opt_res_latest: DataFrame with optimization results
        idx: List of timestamps
        params: Parameters dictionary
        optim_conf: Optimization configuration
        logger: Logger instance
        **common_kwargs: Additional keyword arguments for publish function

    Returns:
        List of column names that were published
    """
    cols_published = []

    # Get custom sensor configuration
    custom_temp = params["passed_data"].get("custom_predicted_temperature_id", [])
    custom_thermal_balance = params["passed_data"].get("custom_thermal_balance_id", [])
    custom_solar = params["passed_data"].get("custom_solar_gain_id", [])

    # Get deferrable load configuration
    def_load_config = optim_conf.get("def_load_config", [])
    if not isinstance(def_load_config, list):
        def_load_config = []

    # Process each thermal load
    for k in range(optim_conf["number_of_deferrable_loads"]):
        if k >= len(def_load_config):
            continue

        load_cfg = def_load_config[k]
        if "thermal_config" not in load_cfg:
            continue

        # 1. Publish predicted temperature
        temp_col_name = f"predicted_temp_heater{k}"
        if temp_col_name in opt_res_latest.columns and k < len(custom_temp):
            entity_conf = custom_temp[k]
            await rh.post_data(
                opt_res_latest[temp_col_name],
                idx,
                entity_conf["entity_id"],
                "temperature",
                entity_conf["unit_of_measurement"],
                entity_conf["friendly_name"],
                type_var="temperature",
                **common_kwargs,
            )
            cols_published.append(temp_col_name)

        # 2. Publish thermal balance (signed: + cooling, - heating)
        thermal_col_name = f"thermal_balance{k}"
        if thermal_col_name in opt_res_latest.columns and k < len(custom_thermal_balance):
            entity_conf = custom_thermal_balance[k]

            # Get thermal balance values
            thermal_balance = opt_res_latest[thermal_col_name]

            # Create attributes with additional metadata
            attributes = {
                "heating_demand": (-thermal_balance.clip(upper=0)).iloc[0],
                "cooling_demand": thermal_balance.clip(lower=0).iloc[0],
                "mode": "cooling"
                if thermal_balance.iloc[0] > 0
                else "heating"
                if thermal_balance.iloc[0] < 0
                else "idle",
                "forecast": thermal_balance.iloc[1:].tolist(),
            }

            # Publish the thermal balance sensor
            await rh.post_data(
                thermal_balance,
                idx,
                entity_conf["entity_id"],
                "energy",
                entity_conf["unit_of_measurement"],
                entity_conf["friendly_name"],
                type_var="thermal_balance",
                attributes=attributes,
                **common_kwargs,
            )
            cols_published.append(thermal_col_name)

        # 3. Publish solar gain
        solar_col_name = f"solar_gain_heater{k}"
        if solar_col_name in opt_res_latest.columns and k < len(custom_solar):
            entity_conf = custom_solar[k]
            await rh.post_data(
                opt_res_latest[solar_col_name],
                idx,
                entity_conf["entity_id"],
                "energy",
                entity_conf["unit_of_measurement"],
                entity_conf["friendly_name"],
                type_var="energy",
                **common_kwargs,
            )
            cols_published.append(solar_col_name)

    return cols_published


def prepare_custom_thermal_balance_ids(num_loads: int, prefix: str = "") -> list[dict[str, str]]:
    """
    Create default custom sensor configuration for thermal balance sensors.

    Args:
        num_loads: Number of deferrable loads
        prefix: Optional prefix for entity IDs

    Returns:
        List of sensor configurations
    """
    custom_ids = []
    for k in range(num_loads):
        custom_ids.append(
            {
                "entity_id": f"{prefix}sensor.thermal_balance{k}",
                "device_class": "energy",
                "unit_of_measurement": "kWh",
                "friendly_name": f"Thermal Balance {k}",
            }
        )
    return custom_ids


def update_thermal_sensor_config(
    passed_data: dict[str, Any], def_load_config: list[dict]
) -> dict[str, Any]:
    """
    Update the sensor configuration to include thermal balance sensors.

    Args:
        passed_data: The passed_data dictionary to update
        def_load_config: Deferrable load configuration list

    Returns:
        Updated passed_data dictionary
    """
    # Count thermal loads
    num_thermal = sum(1 for load in def_load_config if "thermal_config" in load)

    if num_thermal > 0:
        # Create thermal balance sensors if not provided
        if "custom_thermal_balance_id" not in passed_data:
            prefix = passed_data.get("publish_prefix", "")
            passed_data["custom_thermal_balance_id"] = prepare_custom_thermal_balance_ids(
                num_thermal, prefix
            )

    return passed_data
