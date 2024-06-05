"""TOD."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_IP_ADDRESS, CONF_PORT


class ScRpiDevice:
    """TOD."""

    @property
    def hostname(self) -> str:
        """Get the USN TOD set it from configs."""
        return "localhost"

    @property
    def name(self) -> str:
        """Get the name. TOD set it from configs."""
        return "raspberry"

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer. TOD set it from configs."""
        return "Raspberry"

    @property
    def model_name(self) -> str:
        """Get the model name. TOD set it from configs."""
        return "Raspberry Pi 3"


async def async_create_sc_rpi_device(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> ScRpiDevice:
    """Create UPnP/IGD device."""
    # session = async_get_clientsession(hass, verify_ssl=False)
    # requester = AiohttpSessionRequester(session, with_sleep=True, timeout=20)

    # factory = UpnpFactory(requester, non_strict=True)
    # upnp_device = await factory.async_create_device(location)

    # Create profile wrapper.
    reader, writer = await asyncio.open_connection(
        config_entry.data[CONF_IP_ADDRESS], config_entry.data[CONF_PORT]
    )
    device = ScRpiDevice()

    return device
