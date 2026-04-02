"""The vizio component."""

from __future__ import annotations

from pyvizio import VizioAsync

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_TIMEOUT, DEVICE_ID, DOMAIN, VIZIO_DEVICE_CLASSES
from .coordinator import (
    VizioAppsDataUpdateCoordinator,
    VizioConfigEntry,
    VizioDeviceCoordinator,
    VizioRuntimeData,
)
from .services import async_setup_services

DATA_APPS: HassKey[VizioAppsDataUpdateCoordinator] = HassKey(f"{DOMAIN}_apps")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VizioConfigEntry) -> bool:
    """Load the saved entities."""
    host = entry.data[CONF_HOST]
    token = entry.data.get(CONF_ACCESS_TOKEN)
    device_class = entry.data[CONF_DEVICE_CLASS]

    # Create device
    device = VizioAsync(
        DEVICE_ID,
        host,
        entry.data[CONF_NAME],
        auth_token=token,
        device_type=VIZIO_DEVICE_CLASSES[device_class],
        session=async_get_clientsession(hass, False),
        timeout=DEFAULT_TIMEOUT,
    )

    # Create device coordinator
    device_coordinator = VizioDeviceCoordinator(hass, entry, device)
    await device_coordinator.async_config_entry_first_refresh()

    # Create apps coordinator for TVs (shared across entries)
    if device_class == MediaPlayerDeviceClass.TV and DATA_APPS not in hass.data:
        apps_coordinator = VizioAppsDataUpdateCoordinator(hass, Store(hass, 1, DOMAIN))
        await apps_coordinator.async_setup()
        hass.data[DATA_APPS] = apps_coordinator
        await apps_coordinator.async_refresh()

    entry.runtime_data = VizioRuntimeData(
        device_coordinator=device_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VizioConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up apps coordinator if no TV entries remain
    if unload_ok and not any(
        e.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ):
        if apps_coordinator := hass.data.pop(DATA_APPS, None):
            await apps_coordinator.async_shutdown()

    return unload_ok
