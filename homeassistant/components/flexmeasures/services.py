"""Services."""

from datetime import datetime, timedelta
import json
import logging

from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType
import pytz
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .helpers import time_ceil

CHANGE_CONTROL_TYPE_SCHEMA = vol.Schema({vol.Optional("control_type"): str})

SERVICES = [
    {
        "schema": CHANGE_CONTROL_TYPE_SCHEMA,
        "service": "change_control_type",
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # TODO: Is this the correct way and place to set this?
    client = hass.data[DOMAIN]["fm_client"]

    ############
    # Services #
    ############

    async def change_control_type(call: ServiceCall):
        """Change control type S2 Protocol."""
        cem: CEM = hass.data[DOMAIN]["cem"]

        control_type = call.data.get("control_type")

        if control_type not in ControlType:
            LOGGER.exception("TODO")
            return False
        else:
            control_type = ControlType[control_type]
            # print(control_type)

            # await cem.activate_control_type(
            #     control_type=ControlType.FILL_RATE_BASED_CONTROL
            # )

        hass.states.async_set(
            f"{DOMAIN}.cem", json.dumps({"control_type": str(cem._control_type)})
        )  # TODO: expose control type as public property

    async def trigger_and_get_schedule(call: ServiceCall):
        # TODO: not sure what the proper way is to do these things.
        config_data = hass.data[DOMAIN][hass.data[DOMAIN]["config_entry_id"]]

        schedule = await client.trigger_and_get_schedule(
            sensor_id=config_data["power_sensor"],
            start=time_ceil(datetime.now(tz=pytz.utc), timedelta(minutes=15)),
            duration=config_data["schedule_duration"],
            soc_unit=config_data["soc_unit"],
            soc_min=config_data["soc_min"],
            soc_max=config_data["soc_max"],
            consumption_price_sensor=config_data["consumption_price_sensor"],
            production_price_sensor=config_data["production_price_sensor"],
            soc_at_start=call.data.get("soc_at_start"),
        )

        # TODO: create state with sensible name and format
        schedule_state = "ChargeScheduleAvailable" + datetime.now().isoformat()

        hass.states.async_set(
            f"{DOMAIN}.charge_schedule", new_state=schedule_state, attributes=schedule
        )

    async def post_measurements(call: ServiceCall):
        client.post_measurements(
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
        # print(service)
        if "service_func_name" in service:
            service_func_name = service.pop("service_func_name")
            service["service_func"] = locals()[service_func_name]
        hass.services.async_register(DOMAIN, **service)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service["service"])
