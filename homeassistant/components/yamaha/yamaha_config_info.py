"""Configuration Information for Yamaha."""

import logging
from urllib.parse import urlparse

from requests import RequestException
import rxv
from rxv import RXV, ssdp
from rxv.ssdp import RxvDetails

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class YamahaConfigInfo:
    """Check and retrieve configuration Info for Yamaha Receivers."""

    @classmethod
    async def check_yamaha_ssdp(cls, location: str, hass: HomeAssistant) -> bool:
        """Check if the Yamaha receiver has a valid control URL."""
        details: RxvDetails | None = await YamahaConfigInfo.get_rxv_details(
            location, hass
        )
        return (details and details.ctrl_url) is not None

    @classmethod
    async def get_rxv_details(
        cls, location: str, hass: HomeAssistant
    ) -> RxvDetails | None:
        """Retrieve the serial_number and model from the SSDP description URL."""
        info: RxvDetails | None = None
        try:
            info = await hass.async_add_executor_job(ssdp.rxv_details, location)
        except RequestException:
            _LOGGER.warning(
                "Failed to retrieve RXV details from SSDP location: %s", location
            )
        if info is None:
            # Fallback for devices that do not reply to SSDP or fail to reply on the SSDP Url
            # The legacy behaviour is to connect directly to the control Url
            # Note that model_name, friendly_name and serial_number will not be known for those devices
            ctrl_url: str = (
                f"http://{urlparse(location).hostname}:80/YamahaRemoteControl/ctrl"
            )
            result: RXV = await hass.async_add_executor_job(rxv.RXV, ctrl_url)
            info = RxvDetails(
                result.ctrl_url,
                result.unit_desc_url,
                result.model_name,
                result.friendly_name,
                result.serial_number,
            )
        return info
