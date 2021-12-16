"""The 1-Wire component."""
import logging

from pyownet import protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .onewirehub import CannotConnect, OneWireHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a 1-Wire proxy for a config entry."""
    hass.data.setdefault(DOMAIN, {})

    onewirehub = OneWireHub(hass)
    try:
        await onewirehub.initialize(entry)
    except (
        CannotConnect,  # Failed to connect to the server
        protocol.OwnetError,  # Connected to server, but failed to list the devices
    ) as exc:
        raise ConfigEntryNotReady() from exc

    hass.data[DOMAIN][entry.entry_id] = onewirehub

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
