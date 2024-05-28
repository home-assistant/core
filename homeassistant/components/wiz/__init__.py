"""WiZ Platform integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pywizlight import PilotParser, wizlight
from pywizlight.bulb import PIR_SOURCE

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DISCOVER_SCAN_TIMEOUT,
    DISCOVERY_INTERVAL,
    DOMAIN,
    SIGNAL_WIZ_PIR,
    WIZ_CONNECT_EXCEPTIONS,
    WIZ_EXCEPTIONS,
)
from .discovery import async_discover_devices, async_trigger_discovery
from .models import WizData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

REQUEST_REFRESH_DELAY = 0.35

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the wiz integration."""

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT)
        )

    hass.async_create_background_task(_async_discovery(), "wiz-discovery")
    async_track_time_interval(
        hass, _async_discovery, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the wiz integration from a config entry."""
    ip_address = entry.data[CONF_HOST]
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    bulb = wizlight(ip_address)
    try:
        scenes = await bulb.getSupportedScenes()
        await bulb.getMac()
    except WIZ_CONNECT_EXCEPTIONS as err:
        await bulb.async_close()
        raise ConfigEntryNotReady(f"{ip_address}: {err}") from err

    if bulb.mac != entry.unique_id:
        # The ip address of the bulb has changed and its likely offline
        # and another WiZ device has taken the IP. Avoid setting up
        # since its the wrong device. As soon as the device comes back
        # online the ip will get updated and setup will proceed.
        raise ConfigEntryNotReady(
            "Found bulb {bulb.mac} at {ip_address}, expected {entry.unique_id}"
        )

    async def _async_update() -> float | None:
        """Update the WiZ device."""
        try:
            await bulb.updateState()
            if bulb.power_monitoring is not False:
                power: float | None = await bulb.get_power()
                return power
        except WIZ_EXCEPTIONS as ex:
            raise UpdateFailed(f"Failed to update device at {ip_address}: {ex}") from ex
        return None

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

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await bulb.async_close()
        raise

    async def _async_shutdown_on_stop(event: Event) -> None:
        await bulb.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown_on_stop)
    )

    @callback
    def _async_push_update(state: PilotParser) -> None:
        """Receive a push update."""
        _LOGGER.debug("%s: Got push update: %s", bulb.mac, state.pilotResult)
        coordinator.async_set_updated_data(coordinator.data)
        if state.get_source() == PIR_SOURCE:
            async_dispatcher_send(hass, SIGNAL_WIZ_PIR.format(bulb.mac))

    await bulb.start_push(_async_push_update)
    bulb.set_discovery_callback(lambda bulb: async_trigger_discovery(hass, [bulb]))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WizData(
        coordinator=coordinator, bulb=bulb, scenes=scenes
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: WizData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.bulb.async_close()
    return unload_ok
