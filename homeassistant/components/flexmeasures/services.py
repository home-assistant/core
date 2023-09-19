"""Services.."""

from datetime import datetime
import json
import logging
from typing import cast

from flexmeasures_client import FlexMeasuresClient
from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType
import pandas as pd
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    RESOLUTION,
    SCHEDULE_STATE,
    SERVICE_CHANGE_CONTROL_TYPE,
    SIGNAL_UPDATE_SCHEDULE,
    SOC_UNIT,
)
from .exception import UndefinedCEMError, UnknownControlType

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
    client: FlexMeasuresClient = hass.data[DOMAIN]["fm_client"]

    ############
    # Services #
    ############

    async def change_control_type(
        call: ServiceCall,
    ):  # pylint: disable=possibly-unused-variable
        """Change control type S2 Protocol."""

        if "cem" not in hass.data[DOMAIN]:
            raise UndefinedCEMError()

        cem: CEM = hass.data[DOMAIN]["cem"]

        control_type = cast(str, call.data.get("control_type"))

        if not hasattr(ControlType, control_type):
            raise UnknownControlType()

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

        flex_model = client.create_storage_flex_model(
            soc_at_start=call.data.get("soc_at_start"),
            soc_unit=SOC_UNIT,
            soc_max=get_from_option_or_config("soc_max", entry),
            soc_min=get_from_option_or_config("soc_min", entry),
            soc_targets=call.data.get("soc_targets"),
        )
        flex_context = client.create_storage_flex_context(
            consumption_price_sensor=get_from_option_or_config(
                "consumption_price_sensor", entry
            ),
            production_price_sensor=get_from_option_or_config(
                "production_price_sensor", entry
            ),
        )
        schedule_input = {
            "sensor_id": get_from_option_or_config("power_sensor", entry),
            "start": start,
            "duration": get_from_option_or_config("schedule_duration", entry),
            "flex_model": flex_model,
            "flex_context": flex_context,
        }
        LOGGER.info(schedule_input)
        schedule = await client.trigger_and_get_schedule(**schedule_input)

        schedule["values"] = client.convert_units(
            schedule["values"],
            from_unit=schedule["unit"],
            to_unit=UnitOfPower.KILO_WATT,
        )
        schedule = [
            {"start": start + resolution * i, "value": value}
            for i, value in enumerate(schedule["values"])
        ]

        hass.data[DOMAIN][SCHEDULE_STATE]["schedule"] = schedule
        hass.data[DOMAIN][SCHEDULE_STATE]["start"] = start
        hass.data[DOMAIN][SCHEDULE_STATE]["duration"] = get_from_option_or_config(
            "schedule_duration", entry
        )

        async_dispatcher_send(hass, SIGNAL_UPDATE_SCHEDULE)

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


def time_mod(time, delta, epoch=None):
    """From https://stackoverflow.com/a/57877961/13775459."""
    if epoch is None:
        epoch = datetime(1970, 1, 1, tzinfo=time.tzinfo)
    return (time - epoch) % delta


def time_ceil(time, delta, epoch=None):
    """From https://stackoverflow.com/a/57877961/13775459."""
    mod = time_mod(time, delta, epoch)
    if mod:
        return time + (delta - mod)
    return time


def get_from_option_or_config(key: str, entry: ConfigEntry):
    """Get value from the options and, if not found, return the config value."""
    return entry.options.get(key, entry.data.get(key))
