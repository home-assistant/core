"""The lookin integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any

import aiohttp
from aiolookin import (
    Climate,
    LookInHttpProtocol,
    LookinUDPSubscriptions,
    MeteoSensor,
    NoUsableService,
    Remote,
    start_lookin_udp,
)
from aiolookin.models import UDPCommandType, UDPEvent

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    METEO_UPDATE_INTERVAL,
    PLATFORMS,
    REMOTE_UPDATE_INTERVAL,
    TYPE_TO_PLATFORM,
)
from .coordinator import LookinDataUpdateCoordinator, LookinPushCoordinator
from .models import LookinData

LOGGER = logging.getLogger(__name__)

UDP_MANAGER = "udp_manager"


def _async_climate_updater(
    lookin_protocol: LookInHttpProtocol,
    uuid: str,
) -> Callable[[], Coroutine[None, Any, Remote]]:
    """Create a function to capture the cell variable."""

    async def _async_update() -> Climate:
        return await lookin_protocol.get_conditioner(uuid)

    return _async_update


def _async_remote_updater(
    lookin_protocol: LookInHttpProtocol,
    uuid: str,
) -> Callable[[], Coroutine[None, Any, Remote]]:
    """Create a function to capture the cell variable."""

    async def _async_update() -> Remote:
        return await lookin_protocol.get_remote(uuid)

    return _async_update


class LookinUDPManager:
    """Manage the lookin UDP subscriptions."""

    def __init__(self) -> None:
        """Init the manager."""
        self._lock = asyncio.Lock()
        self._listener: Callable | None = None
        self._subscriptions: LookinUDPSubscriptions | None = None

    async def async_get_subscriptions(self) -> LookinUDPSubscriptions:
        """Get the shared LookinUDPSubscriptions."""
        async with self._lock:
            if not self._listener:
                self._subscriptions = LookinUDPSubscriptions()
                self._listener = await start_lookin_udp(self._subscriptions, None)
            return self._subscriptions

    async def async_stop(self) -> None:
        """Stop the listener."""
        async with self._lock:
            assert self._listener is not None
            self._listener()
            self._listener = None
            self._subscriptions = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lookin from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    lookin_protocol = LookInHttpProtocol(
        api_uri=f"http://{host}", session=async_get_clientsession(hass)
    )

    try:
        lookin_device = await lookin_protocol.get_info()
        devices = await lookin_protocol.get_devices()
    except (TimeoutError, aiohttp.ClientError, NoUsableService) as ex:
        raise ConfigEntryNotReady from ex

    if entry.unique_id != (found_uuid := lookin_device.id.upper()):
        # If the uuid of the device does not match the unique_id
        # of the config entry, it likely means the DHCP lease has expired
        # and the device has been assigned a new IP address. We need to
        # wait for the next discovery to find the device at its new address
        # and update the config entry so we do not mix up devices.
        raise ConfigEntryNotReady(
            f"Unexpected device found at {host}; expected {entry.unique_id}, "
            f"found {found_uuid}"
        )

    push_coordinator = LookinPushCoordinator(entry.title)

    if lookin_device.model >= 2:
        coordinator_class = LookinDataUpdateCoordinator[MeteoSensor]
        meteo_coordinator = coordinator_class(
            hass,
            push_coordinator,
            name=entry.title,
            update_method=lookin_protocol.get_meteo_sensor,
            update_interval=METEO_UPDATE_INTERVAL,  # Updates are pushed (fallback is polling)
        )
        await meteo_coordinator.async_config_entry_first_refresh()

    device_coordinators: dict[str, LookinDataUpdateCoordinator[Remote]] = {}
    for remote in devices:
        if (platform := TYPE_TO_PLATFORM.get(remote["Type"])) is None:
            continue
        uuid = remote["UUID"]
        if platform == Platform.CLIMATE:
            updater = _async_climate_updater(lookin_protocol, uuid)
        else:
            updater = _async_remote_updater(lookin_protocol, uuid)
        coordinator = LookinDataUpdateCoordinator(
            hass,
            push_coordinator,
            name=f"{entry.title} {uuid}",
            update_method=updater,
            update_interval=REMOTE_UPDATE_INTERVAL,  # Updates are pushed (fallback is polling)
        )
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[uuid] = coordinator

    @callback
    def _async_meteo_push_update(event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for meteo sensor: %s", event)
        meteo: MeteoSensor = meteo_coordinator.data
        meteo.update_from_value(event.value)
        meteo_coordinator.async_set_updated_data(meteo)

    if UDP_MANAGER not in domain_data:
        manager = domain_data[UDP_MANAGER] = LookinUDPManager()
    else:
        manager = domain_data[UDP_MANAGER]

    lookin_udp_subs = await manager.async_get_subscriptions()

    if lookin_device.model >= 2:
        entry.async_on_unload(
            lookin_udp_subs.subscribe_event(
                lookin_device.id, UDPCommandType.meteo, None, _async_meteo_push_update
            )
        )

    hass.data[DOMAIN][entry.entry_id] = LookinData(
        host=host,
        lookin_udp_subs=lookin_udp_subs,
        lookin_device=lookin_device,
        meteo_coordinator=meteo_coordinator if lookin_device.model >= 2 else None,
        devices=devices,
        lookin_protocol=lookin_protocol,
        device_coordinators=device_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        manager: LookinUDPManager = hass.data[DOMAIN][UDP_MANAGER]
        await manager.async_stop()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove lookin config entry from a device."""
    data: LookinData = hass.data[DOMAIN][entry.entry_id]
    all_identifiers: set[tuple[str, str]] = {
        (DOMAIN, data.lookin_device.id),
        *((DOMAIN, remote["UUID"]) for remote in data.devices),
    }
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier in all_identifiers
    )
