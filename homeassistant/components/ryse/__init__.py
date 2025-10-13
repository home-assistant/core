import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ryseble.device import RyseBLEDevice

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the RYSE component."""
    _LOGGER.debug("Setting up RYSE Device integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up RYSE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    device = RyseBLEDevice(
        address=entry.data["address"],
        rx_uuid=entry.data["rx_uuid"],
        tx_uuid=entry.data["tx_uuid"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["cover"])

    return True
