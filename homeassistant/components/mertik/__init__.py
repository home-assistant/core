import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import MertikDataCoordinator
from .mertik import Mertik

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "number", "sensor", "light", "climate", "select"]

type MertikConfigEntry = ConfigEntry[MertikDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MertikConfigEntry) -> bool:
    """Set up the Mertik component."""
    try:
        mertik = await Mertik.async_connect(entry.data[CONF_HOST])
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    coordinator = MertikDataCoordinator(hass, mertik, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MertikConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow the user to remove the device via the HA UI."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MertikConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.mertik.close()
    return unloaded
