"""Configuration Information for Yamaha."""

from rxv import ssdp
from rxv.ssdp import RxvDetails

from homeassistant.core import HomeAssistant


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
        return await hass.async_add_executor_job(ssdp.rxv_details, location)
