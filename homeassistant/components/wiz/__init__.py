"""WiZ Platform integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from pywizlight import wizlight
from pywizlight.exceptions import WizLightNotKnownBulb

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DISCOVER_SCAN_TIMEOUT, DISCOVERY_INTERVAL, DOMAIN, WIZ_EXCEPTIONS
from .discovery import async_discover_devices, async_trigger_discovery
from .models import WizData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.SWITCH]

REQUEST_REFRESH_DELAY = 0.35


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the wiz integration."""

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    asyncio.create_task(_async_discovery())
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the wiz integration from a config entry."""
    ip_address = entry.data[CONF_HOST]
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    bulb = wizlight(ip_address)
    try:
        scenes = await bulb.getSupportedScenes()
        await bulb.getMac()
    except (WizLightNotKnownBulb, *WIZ_EXCEPTIONS) as err:
        raise ConfigEntryNotReady(f"{ip_address}: {err}") from err

    async def _async_update() -> None:
        """Update the WiZ device."""
        try:
            await bulb.updateState()
        except WIZ_EXCEPTIONS as ex:
            raise UpdateFailed(f"Failed to update device at {ip_address}: {ex}") from ex

    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=entry.title,
        update_interval=timedelta(seconds=15),
        update_method=_async_update,
        # We don't want an immediate refresh since the device
        # takes a moment to reflect the state change
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
        ),
    )

    await bulb.start_push(lambda _: coordinator.async_set_updated_data(None))
    bulb.set_discovery_callback(lambda bulb: async_trigger_discovery(hass, [bulb]))
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WizData(
        coordinator=coordinator, bulb=bulb, scenes=scenes
    )
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: WizData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.bulb.async_close()
    return unload_ok
