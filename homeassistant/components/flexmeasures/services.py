"""Services.."""

from datetime import datetime
import json
import logging
from typing import cast

from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType
import pandas as pd
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.util.dt as dt_util

from .const import DOMAIN, RESOLUTION, SERVICE_CHANGE_CONTROL_TYPE
from .helpers import get_from_option_or_config, time_ceil

CHANGE_CONTROL_TYPE_SCHEMA = vol.Schema({vol.Optional("control_type"): str})

SERVICES = [
    {
        "schema": CHANGE_CONTROL_TYPE_SCHEMA,
        "service": SERVICE_CHANGE_CONTROL_TYPE,
        "service_func_name": "change_control_type",
    },
    {
        "schema": None,
        "service": "trigger_and_get_schedule",
        "service_func_name": "trigger_and_get_schedule",
    },
    {
        "schema": None,
        "service": "post_measurements",
        "service_func_name": "post_measurements",
    },
]

LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up services."""

    # Is this the correct way and place to set this?
    client = hass.data[DOMAIN]["fm_client"]

    ############
    # Services #
    ############

    async def change_control_type(
        call: ServiceCall,
    ):  # pylint: disable=possibly-unused-variable
        """Change control type S2 Protocol."""
        cem: CEM = hass.data[DOMAIN]["cem"]
        control_type = cast(str, call.data.get("control_type"))

        if not hasattr(ControlType, control_type):
            LOGGER.exception("TODO")
            return False

        control_type = ControlType[control_type]

        await cem.activate_control_type(control_type=control_type)

        hass.states.async_set(
            f"{DOMAIN}.cem", json.dumps({"control_type": str(cem.control_type)})
        )

    async def trigger_and_get_schedule(
        call: ServiceCall,
    ):  # pylint: disable=possibly-unused-variable
        resolution = pd.Timedelta(RESOLUTION)
        tzinfo = dt_util.get_time_zone(hass.config.time_zone)
        start = time_ceil(datetime.now(tz=tzinfo), resolution)

        input_arguments = {
            "sensor_id": get_from_option_or_config("power_sensor", entry),
            "start": start,
            "duration": get_from_option_or_config("schedule_duration", entry),
            "soc_unit": "MWh",
            "soc_min": get_from_option_or_config("soc_min", entry),
            "soc_max": get_from_option_or_config("soc_max", entry),
            "consumption_price_sensor": get_from_option_or_config(
                "consumption_price_sensor", entry
            ),
            "production_price_sensor": get_from_option_or_config(
                "production_price_sensor", entry
            ),
            "soc_at_start": call.data.get("soc_at_start"),
        }

        schedule = await client.trigger_and_get_schedule(
            soc_at_start=call.data.get("soc_at_start"), **input_arguments
        )

        schedule_state = start.isoformat()
        schedule = [
            {"start": start + resolution * i, "value": value}
            for i, value in enumerate(schedule["values"])
        ]

        hass.states.async_set(
            f"{DOMAIN}.charge_schedule",
            new_state=schedule_state,
            attributes={"schedule": schedule},
        )

    async def post_measurements(
        call: ServiceCall,
    ):  # pylint: disable=possibly-unused-variable
        await client.post_measurements(
            sensor_id=call.data.get("sensor_id"),
            start=call.data.get("start"),
            duration=call.data.get("duration"),
            values=call.data.get("values"),
            unit=call.data.get("unit"),
            prior=call.data.get("prior"),
        )

    #####################
    # Register services #
    #####################

    for service in SERVICES:
        if "service_func_name" in service:
            service_func_name = service.pop("service_func_name")
            service["service_func"] = locals()[service_func_name]

        hass.services.async_register(DOMAIN, **service)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    for service in SERVICES:
        if hass.services.has_service(DOMAIN, service["service"]):
            hass.services.async_remove(DOMAIN, service["service"])
