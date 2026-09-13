"""The Denon AVR Network Receivers integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from denonavr import DenonAVR
from denonavr.const import ALL_TELNET_EVENTS
from denonavr.exceptions import AvrNetworkError, AvrTimoutError

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
    TELNET_EVENTS,
)
from .coordinator import DenonAvrDataUpdateCoordinator, async_refresh_status
from .receiver import ConnectDenonAVR
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT, Platform.SWITCH]

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
        entry.options.get(CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY),
        lambda: get_async_client(hass),
    )
    try:
        await connect_denonavr.async_connect_receiver()
    except (AvrNetworkError, AvrTimoutError) as ex:
        raise ConfigEntryNotReady from ex
    receiver = connect_denonavr.receiver
    assert receiver is not None

    update_audyssey = entry.options.get(CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY)
    update_interval = timedelta(seconds=COORDINATOR_UPDATE_INTERVAL)

    # Shared by both coordinators and all commands to serialize receiver
    # access. Created once here, not derived from the receiver: denonavr's
    # attrs classes are unhashable, so they can't be dict/weak-ref keys.
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
    # A receiver that can't be reached for basic status right after a
    # successful connection is exceptional enough to treat as "not
    # ready" (matches this integration's existing behavior).
    await coordinator.async_config_entry_first_refresh()

    audyssey_coordinator = DenonAvrDataUpdateCoordinator(
        hass,
        entry,
        receiver,
        lock,
        name="audyssey",
        # Only polls on a recurring schedule if the (opt-in, since a
        # fetch can reportedly take up to ~10s on some receivers)
        # "Update Audyssey settings" option is on. Either way, it can
        # still be asked to refresh on demand via async_request_refresh
        # - the select/switch entities do exactly that right after
        # their own actions, regardless of this option.
        update_interval=update_interval if update_audyssey else None,
        refresh_fn=lambda r: r.async_update_audyssey(),
    )
    # Audyssey values (dynamic_eq, reference_level_offset, dynamic_volume,
    # multi_eq) aren't populated by the receiver's regular status queries
    # at all, so without this the entities backed by them would start
    # (and without Telnet, stay) unavailable. Not every receiver
    # supports Audyssey though, so a failure here shouldn't block setup
    # the way the main coordinator's failure does - just leave those
    # entities unavailable, as expected.
    await audyssey_coordinator.async_refresh()

    @callback
    def _propagate_connectivity_to_audyssey() -> None:
        """Reflect the status coordinator's connectivity into this one.

        Only when the Audyssey coordinator has no recurring poll of
        its own (update_interval=None) - otherwise it would never
        learn the receiver went offline. When it does poll on its own
        schedule, an unrelated general-status success shouldn't
        overwrite its own last_update_success - that would mark it
        recovered without an actual Audyssey refresh confirming it.
        """
        if audyssey_coordinator.update_interval is not None:
            return
        if audyssey_coordinator.last_update_success != coordinator.last_update_success:
            audyssey_coordinator.last_update_success = coordinator.last_update_success
            audyssey_coordinator.async_update_listeners()

    entry.async_on_unload(
        coordinator.async_add_listener(_propagate_connectivity_to_audyssey)
    )

    @callback
    def _telnet_notify_audyssey(zone: str, event: str, parameter: str) -> None:
        """Notify Audyssey listeners of Telnet activity.

        Registered on the receiver directly rather than through the
        media_player entity: that entity's own callback only runs
        while it's enabled, but the receiver stays updated via Telnet
        regardless, so Audyssey entities need a path independent of it.
        """
        if event not in TELNET_EVENTS:
            return
        audyssey_coordinator.async_update_listeners()

    receiver.register_callback(ALL_TELNET_EVENTS, _telnet_notify_audyssey)
    entry.async_on_unload(
        lambda: receiver.unregister_callback(ALL_TELNET_EVENTS, _telnet_notify_audyssey)
    )

    entry.runtime_data = DenonAvrData(
        receiver=receiver,
        coordinator=coordinator,
        audyssey_coordinator=audyssey_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    use_telnet = entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET)

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
