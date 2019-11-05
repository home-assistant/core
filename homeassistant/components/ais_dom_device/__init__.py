"""
Support for interacting with Ais Dom devices.

For more details about this platform, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import asyncio
from .config_flow import configured_service
from .const import DOMAIN

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

    hass.services.async_register(
        DOMAIN, "convert_rf_code_b1_to_b0", convert_rf_code_b1_to_b0
    )

    return True


def _convert_rf_code_b1_to_b0(code):
    return "123" + str(code)
