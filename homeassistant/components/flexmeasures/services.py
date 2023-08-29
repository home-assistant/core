"""Services."""

import json
import logging

from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

CHANGE_CONTROL_TYPE_SCHEMA = vol.Schema({vol.Optional("control_type"): str})

SERVICES = [
    {
        "schema": CHANGE_CONTROL_TYPE_SCHEMA,
        "service": "change_control_type",
        "service_func_name": "change_control_type",
    }
]

LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    ############
    # Services #
    ############

    async def change_control_type(call: ServiceCall):
        """Change control type S2 Protocol."""
        cem: CEM = hass.data[DOMAIN]["cem"]

        control_type = call.data.get("control_type")
        print(control_type)
        print(hasattr(ControlType, control_type))
        if not hasattr(ControlType, control_type):
            LOGGER.exception("TODO")
            return False
        else:
            control_type = getattr(ControlType, control_type)

            await cem.activate_control_type(
                control_type=ControlType.FILL_RATE_BASED_CONTROL
            )

        hass.states.async_set(
            f"{DOMAIN}.cem", json.dumps({"control_type": str(cem._control_type)})
        )  # TODO: expose control type as public property

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
