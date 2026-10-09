"""The WiLight integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .parent_device import WiLightConfigEntry, WiLightParent
from .services import async_setup_services

# List the platforms that you want to support.
PLATFORMS = [Platform.COVER, Platform.FAN, Platform.LIGHT, Platform.SWITCH]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WiLight integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WiLightConfigEntry) -> bool:
    """Set up a wilight config entry."""

    parent = WiLightParent(hass, entry)

    if not await parent.async_setup():
        raise ConfigEntryNotReady

    entry.runtime_data = parent

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WiLightConfigEntry) -> bool:
    """Unload WiLight config entry."""

    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup
    await entry.runtime_data.async_reset()

    return unload_ok
