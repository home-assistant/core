"""
Support for interacting with Ais Dom devices.

For more details about this platform, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import asyncio
from .config_flow import configured_service
from .const import DOMAIN
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Ais Dom devices platform."""
    _LOGGER.info("async_setup Ais Dom devices platform.")

    # register services
    def convert_rf_code_b1_to_b0(call):
        if "code" not in call.data:
            _LOGGER.error("No code to convert")
            return
        _convert_rf_code_b1_to_b0(call.data["code"])

    def add_new_rf433_switch(call):
        if "name" not in call.data:
            return
        if "codes" not in call.data:
            return
        _add_new_rf433_switch(hass, call.data["name"], call.data["codes"])

    hass.services.async_register(
        DOMAIN, "convert_rf_code_b1_to_b0", convert_rf_code_b1_to_b0
    )
    hass.services.async_register(DOMAIN, "add_new_rf433_switch", add_new_rf433_switch)

    return True


def _convert_rf_code_b1_to_b0(code):
    _LOGGER.info("TODO 123" + str(code))


def _add_new_rf433_switch(hass, name, codes):
    # 1. select the best code and convert it to B0

    # 2. save this code and his mane in json

    # 3. execute the discovery
    yield from hass.services.async_call(
        "mqtt", "publish", {"topic": "dom/cmnd/SetOption19", "payload": 1}
    )

    pass
