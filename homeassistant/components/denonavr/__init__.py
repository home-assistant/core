"""The Denon AVR Network Receivers integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from denonavr import DenonAVR
from denonavr.exceptions import AvrRequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SHOW_ALL_SOURCES,
    CONF_UPDATE_AUDYSSEY,
    CONF_USE_TELNET,
    CONF_ZONE2,
    CONF_ZONE3,
    COORDINATOR_UPDATE_INTERVAL,
    DEFAULT_SHOW_SOURCES,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_AUDYSSEY,
    DEFAULT_USE_TELNET,
    DEFAULT_ZONE2,
    DEFAULT_ZONE3,
    DOMAIN,
)
from .coordinator import (
    DenonAvrDataUpdateCoordinator,
    async_refresh_audyssey,
    async_refresh_status,
    mark_unavailable,
)
from .receiver import ConnectDenonAVR
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DenonAvrData:
    """Runtime data for a Denon AVR config entry."""

    receiver: DenonAVR
    coordinator: DenonAvrDataUpdateCoordinator
    audyssey_coordinator: DenonAvrDataUpdateCoordinator


type DenonavrConfigEntry = ConfigEntry[DenonAvrData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DenonavrConfigEntry) -> bool:
    """Set up the denonavr components from a config entry."""
    # Connect to receiver
    connect_denonavr = ConnectDenonAVR(
        entry.data[CONF_HOST],
        DEFAULT_TIMEOUT,
        entry.options.get(CONF_SHOW_ALL_SOURCES, DEFAULT_SHOW_SOURCES),
        entry.options.get(CONF_ZONE2, DEFAULT_ZONE2),
        entry.options.get(CONF_ZONE3, DEFAULT_ZONE3),
        entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET),
        lambda: get_async_client(hass),
    )
    try:
        await connect_denonavr.async_connect_receiver()
    except AvrRequestError as ex:
        raise ConfigEntryNotReady from ex
    receiver = connect_denonavr.receiver
    assert receiver is not None

    update_audyssey = entry.options.get(CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY)
    use_telnet = entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET)
    update_interval = timedelta(seconds=COORDINATOR_UPDATE_INTERVAL)

    # Serializes receiver access across both coordinators and every command.
    # Not derived from the receiver: denonavr's attrs classes are unhashable.
    lock = asyncio.Lock()

    coordinator = DenonAvrDataUpdateCoordinator(
        hass,
        entry,
        receiver,
        lock,
        name="status",
        update_interval=update_interval,
        refresh_fn=async_refresh_status,
    )
    # Reads only without Telnet: with it, receiver.py already read status
    # before connecting, so this is skipped. Either read failing is not ready.
    await coordinator.async_config_entry_first_refresh()

    audyssey_coordinator = DenonAvrDataUpdateCoordinator(
        hass,
        entry,
        receiver,
        lock,
        name="audyssey",
        # Opt-in because the fetch can take ~10s. It governs the recurring
        # poll alone: entities still confirm their own actions on demand.
        update_interval=update_interval if update_audyssey else None,
        refresh_fn=async_refresh_audyssey,
    )
    coordinator.peer = audyssey_coordinator
    audyssey_coordinator.peer = coordinator

    @callback
    def _propagate_connectivity_to_audyssey() -> None:
        """Reflect the status coordinator's connectivity into this one.

        Only while this coordinator has no poll of its own. One that polls
        reads on its next interval, since this failure forces it to, and its
        own read is the better evidence either way.
        """
        if audyssey_coordinator.polls:
            return
        if audyssey_coordinator.last_update_success != coordinator.last_update_success:
            audyssey_coordinator.last_update_success = coordinator.last_update_success
            audyssey_coordinator.async_update_listeners()

    entry.async_on_unload(
        coordinator.async_add_internal_listener(_propagate_connectivity_to_audyssey)
    )

    @callback
    def _propagate_audyssey_failure_to_general() -> None:
        """Reflect a confirmed Audyssey connectivity failure into the status one.

        Only while the status coordinator has no poll of its own. One that
        polls reads on its next interval even with Telnet healthy, since this
        failure forces it to. Failure only; recovery is that coordinator's own
        to confirm.
        """
        if not audyssey_coordinator.last_update_success and not coordinator.polls:
            mark_unavailable(coordinator)

    entry.async_on_unload(
        audyssey_coordinator.async_add_internal_listener(
            _propagate_audyssey_failure_to_general
        )
    )

    # Nothing else populates these values: status queries skip them and Telnet
    # only pushes on a change. Forced, and after the listener above so a
    # failure reaches the status coordinator instead of failing setup.
    await audyssey_coordinator.async_refresh_forced()

    entry.runtime_data = DenonAvrData(
        receiver=receiver,
        coordinator=coordinator,
        audyssey_coordinator=audyssey_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from Telnet."""
        if use_telnet:
            await receiver.async_telnet_disconnect()

    if use_telnet:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DenonavrConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if config_entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET):
        receiver = config_entry.runtime_data.receiver
        await receiver.async_telnet_disconnect()

    # Remove zone2 and zone3 entities if needed
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    unique_id = config_entry.unique_id or config_entry.entry_id
    zone2_id = f"{unique_id}-Zone2"
    zone3_id = f"{unique_id}-Zone3"
    for entry in entries:
        if entry.unique_id == zone2_id and not config_entry.options.get(CONF_ZONE2):
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.debug("Removing zone2 from DenonAvr")
        if entry.unique_id == zone3_id and not config_entry.options.get(CONF_ZONE3):
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.debug("Removing zone3 from DenonAvr")

    return unload_ok
