"""The RFM Gateway integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import (
    RfmCapabilities,
    RfmGatewayClient,
    RfmGatewayConnectionError,
    RfmGatewayProtocolError,
)
from .const import CONF_HOST, DOMAIN

__all__ = [
    "CONF_HOST",
    "DOMAIN",
    "RfmCapabilities",
    "RfmGatewayClient",
    "RfmGatewayConnectionError",
    "RfmGatewayProtocolError",
]

PLATFORMS: list[Platform] = [Platform.RADIO_FREQUENCY]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RFM Gateway from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RFM Gateway config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
