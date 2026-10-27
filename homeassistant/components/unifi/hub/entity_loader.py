"""UniFi Network entity loader.

Central point to load entities for the different platforms.
Make sure expected clients are available for platforms.
"""

import asyncio
from collections.abc import Callable, Coroutine, Iterator, Sequence
from datetime import datetime, timedelta
from functools import partial
import json
from typing import TYPE_CHECKING, Any

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.models.api import ApiItem
from aiounifi.models.client import Client

from homeassistant.const import Platform
from homeassistant.core import async_noop, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import CLIENT_RESTORE_MAX_AGE, LOGGER, UNIFI_WIRELESS_CLIENTS
from ..coordinator import UPDATE_TIMEOUT, UnifiDataUpdateCoordinator
from ..entity import UnifiEntity, UnifiEntityDescription
from .connection import ACCOUNT_ERRORS, LOGIN_ERRORS, NOT_READY_ERRORS, REQUEST_TIMEOUT

if TYPE_CHECKING:
    from .hub import UnifiHub

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiEntityLoader:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(self, hub: UnifiHub) -> None:
        """Initialize the UniFi entity loader."""
        self.hub = hub
        self._startup_only_api_updaters = (self._async_update_clients_all,)
        self.wireless_clients = hub.hass.data[UNIFI_WIRELESS_CLIENTS]

        self._data_coordinators: dict[int, UnifiDataUpdateCoordinator[Any]] = {
            id(hub.api.clients): UnifiDataUpdateCoordinator(hub, hub.api.clients),
            id(hub.api.devices): UnifiDataUpdateCoordinator(hub, hub.api.devices),
            id(hub.api.dpi_apps): UnifiDataUpdateCoordinator(hub, hub.api.dpi_apps),
            id(hub.api.dpi_groups): UnifiDataUpdateCoordinator(hub, hub.api.dpi_groups),
            id(hub.api.firewall_policies): UnifiDataUpdateCoordinator(
                hub, hub.api.firewall_policies
            ),
            id(hub.api.object_oriented_network_configs): UnifiDataUpdateCoordinator(
                hub,
                hub.api.object_oriented_network_configs,
                disable_polling_on_endpoint_not_found=True,
            ),
            id(hub.api.port_forwarding): UnifiDataUpdateCoordinator(
                hub, hub.api.port_forwarding
            ),
            id(hub.api.traffic_rules): UnifiDataUpdateCoordinator(
                hub, hub.api.traffic_rules
            ),
            id(hub.api.traffic_routes): UnifiDataUpdateCoordinator(
                hub, hub.api.traffic_routes
            ),
            id(hub.api.wlans): UnifiDataUpdateCoordinator(hub, hub.api.wlans),
        }
        self._data_coordinator_aliases: dict[int, int] = {
            id(hub.api.outlets): id(hub.api.devices),
            id(hub.api.ports): id(hub.api.devices),
        }
        for coordinator in self._data_coordinators.values():
            self.hub.config.entry.async_on_unload(
                coordinator.async_add_listener(async_noop)
            )

        self.platforms: list[
            tuple[
                AddEntitiesCallback,
                type[UnifiEntity],
                tuple[UnifiEntityDescription, ...],
                bool,
            ]
        ] = []

        self.known_objects: set[tuple[str, str]] = set()
        """Tuples of entity description key and object ID of loaded entities."""

    async def async_load_sites(self) -> None:
        """Load the sites of the console."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.hub.api.sites.update()
        except ACCOUNT_ERRORS as err:
            raise ConfigEntryAuthFailed from err
        except (
            TimeoutError,
            json.JSONDecodeError,
            aiounifi.AiounifiException,
        ) as err:
            raise ConfigEntryNotReady(
                "UniFi site information is not available"
            ) from err
        if not self.hub.api.sites.values():
            raise ConfigEntryNotReady("UniFi Network has not listed any site yet")

    async def initialize(self) -> None:
        """Initialize API data and extra client support."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await self.hub.api.system_information.update()
        except ACCOUNT_ERRORS as err:
            raise ConfigEntryAuthFailed from err
        except (*NOT_READY_ERRORS, *LOGIN_ERRORS) as err:
            # A booting console can reject a login for a moment, and the site
            # list right before was readable
            raise ConfigEntryNotReady("UniFi Network application is not ready") from err
        except aiounifi.AiounifiException as err:
            # The application answers, other data can still be loaded
            LOGGER.debug("UniFi Network answered system information with: %r", err)

        await asyncio.gather(
            self._refresh_data(self._startup_only_api_updaters),
            self._refresh_data(
                [
                    coordinator.async_refresh
                    for coordinator in self._data_coordinators.values()
                ]
            ),
        )
        self._restore_inactive_clients()
        self._prune_client_trackers()
        self._prune_unlisted_devices()
        self.wireless_clients.update_clients(set(self.hub.api.clients.values()))

    async def _async_update_clients_all(self) -> None:
        """Load all known clients to restore inactive ones."""
        async with asyncio.timeout(UPDATE_TIMEOUT):
            await self.hub.api.clients_all.update()

    async def async_resync(self) -> None:
        """Refetch all handler data after a connection is restored."""
        await asyncio.gather(
            *(
                coordinator.async_resync()
                for coordinator in self._data_coordinators.values()
            )
        )

    async def _refresh_data(
        self, updaters: Sequence[Callable[[], Coroutine[Any, Any, None]]]
    ) -> None:
        results = await asyncio.gather(
            *[update() for update in updaters],
            return_exceptions=True,
        )
        for result in results:
            if result is not None:
                LOGGER.warning("Exception on update %s", result)

    @callback
    def _restore_inactive_clients(self) -> None:
        """Restore recently seen inactive clients.

        The UniFi controller keeps a record of every client it has ever seen.
        Only clients seen within the retention window, or explicitly selected
        or blocked, are restored.
        """
        api = self.hub.api
        now = dt_util.utcnow()
        always_restore = self._always_restore_clients()

        for _, mac in self._client_trackers():
            if mac in api.clients or mac in always_restore:
                continue

            # An adopted network device keeps its client record from before
            # adoption, which would bring its old client tracker back
            if mac in api.devices:
                continue

            client = api.clients_all.get(mac)
            if client is not None and not self._client_is_stale(client, now):
                api.clients.process_raw([dict(client.raw)])

        for mac in always_restore:
            if mac not in api.clients and mac in api.clients_all:
                api.clients.process_raw([dict(api.clients_all[mac].raw)])

    @callback
    def _prune_client_trackers(self) -> None:
        """Remove trackers of stale clients and of clients no longer listed.

        Their device is removed with them so the registry does not grow
        unbounded.
        """
        api = self.hub.api
        entity_registry = er.async_get(self.hub.hass)
        device_registry = dr.async_get(self.hub.hass)
        now = dt_util.utcnow()
        always_restore = self._always_restore_clients()

        # A client missing from clients_all only means it was removed from the
        # controller when that list loaded. A failed fetch leaves it empty,
        # which would otherwise wipe every tracker and its device.
        prune_unlisted = bool(api.clients_all.values())
        # A failed devices fetch can be swallowed, leaving the list empty, and a
        # network device then can't be told apart from a client sharing its MAC
        devices_loaded = bool(api.devices.values())

        pruned = 0
        for entity_id, mac in self._client_trackers():
            if mac in api.clients or mac in always_restore:
                continue

            # An adopted network device shares the MAC, so only its old client
            # tracker goes, not the device
            if mac in api.devices:
                entity_registry.async_remove(entity_id)
                pruned += 1
                continue

            if (client := api.clients_all.get(mac)) is None:
                if not prune_unlisted:
                    continue
            elif not self._client_is_stale(client, now):
                continue

            if not devices_loaded:
                continue

            self._remove_client(entity_registry, device_registry, entity_id, mac)
            pruned += 1

        if pruned:
            LOGGER.debug("Pruned %s UniFi client tracker(s)", pruned)

    @callback
    def _always_restore_clients(self) -> set[str]:
        """Return the MACs of clients selected or blocked in the options."""
        config = self.hub.config
        return {*config.option_supported_clients, *config.option_block_clients}

    @callback
    def _client_trackers(self) -> Iterator[tuple[str, str]]:
        """Yield the entity ID and MAC of each client tracker in the registry."""
        for entry in er.async_entries_for_config_entry(
            er.async_get(self.hub.hass), self.hub.config.entry.entry_id
        ):
            if entry.domain == Platform.DEVICE_TRACKER and "-" in entry.unique_id:
                yield entry.entity_id, entry.unique_id.split("-", 1)[1]

    @callback
    def _client_is_stale(self, client: Client, now: datetime) -> bool:
        """Return if a client has not been seen within the retention window."""
        last_seen = dt_util.utc_from_timestamp(client.last_seen or 0)
        return now - last_seen > CLIENT_RESTORE_MAX_AGE

    @callback
    def _remove_client(
        self,
        entity_registry: er.EntityRegistry,
        device_registry: dr.DeviceRegistry,
        entity_id: str,
        mac: str,
    ) -> None:
        """Remove a client's tracker entity and its device."""
        entity_registry.async_remove(entity_id)
        if device := device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), self.hub.config.entry.entry_id
        ):
            device_registry.async_remove_device(device.id)

    @callback
    def _prune_unlisted_devices(self) -> None:
        """Remove devices whose MAC the controller no longer lists.

        Catches client devices without a tracker, such as those holding only a
        link speed sensor, or nothing at all after their entities were removed,
        and network devices removed from the controller.
        """
        api = self.hub.api
        # A failed fetch leaves its list empty, and network devices aren't
        # necessarily in clients_all, so both lists have to be loaded before a
        # device missing from them is taken as removed
        if not api.clients_all.values() or not api.devices.values():
            return

        device_registry = dr.async_get(self.hub.hass)
        keep = self._always_restore_clients()
        pruned = 0
        for device in dr.async_entries_for_config_entry(
            device_registry, self.hub.config.entry.entry_id
        ):
            macs = {
                value
                for connection_type, value in device.connections
                if connection_type == dr.CONNECTION_NETWORK_MAC
            }
            if not macs or any(
                mac in api.clients
                or mac in api.clients_all
                or mac in api.devices
                or mac in keep
                for mac in macs
            ):
                continue
            device_registry.async_remove_device(device.id)
            pruned += 1

        if pruned:
            LOGGER.debug("Pruned %s UniFi device(s) no longer listed", pruned)

    @callback
    def register_platform(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_class: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        requires_admin: bool = False,
    ) -> None:
        """Register UniFi entity platforms."""
        self.platforms.append(
            (async_add_entities, entity_class, descriptions, requires_admin)
        )

    @callback
    def load_entities(self) -> None:
        """Load entities into the registered UniFi platforms."""
        for (
            async_add_entities,
            entity_class,
            descriptions,
            requires_admin,
        ) in self.platforms:
            if requires_admin and not self.hub.is_admin:
                continue
            self._load_entities(entity_class, descriptions, async_add_entities)

    @callback
    def _should_add_entity(
        self, description: UnifiEntityDescription, obj_id: str
    ) -> bool:
        """Validate if entity is allowed and supported before creating it."""
        return bool(
            (description.key, obj_id) not in self.known_objects
            and description.allowed_fn(self.hub, obj_id)
            and description.supported_fn(self.hub, obj_id)
        )

    @callback
    def get_data_update_coordinator[HandlerT: APIHandler[ApiItem]](
        self, handler: HandlerT
    ) -> UnifiDataUpdateCoordinator[HandlerT]:
        """Return the data coordinator for a handler."""
        handler_id = id(handler)
        resolved_handler_id = self._data_coordinator_aliases.get(handler_id, handler_id)
        return self._data_coordinators[resolved_handler_id]

    @callback
    def _load_entities(
        self,
        unifi_platform_entity: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Load entities and subscribe for future entities."""

        @callback
        def add_unifi_entities() -> None:
            """Add currently known UniFi entities."""
            async_add_entities(
                unifi_platform_entity(obj_id, self.hub, description)
                for description in descriptions
                for obj_id in description.api_handler_fn(self.hub.api)
                if self._should_add_entity(description, obj_id)
            )

        add_unifi_entities()

        self.hub.config.entry.async_on_unload(
            async_dispatcher_connect(
                self.hub.hass,
                self.hub.signal_options_update,
                add_unifi_entities,
            )
        )

        # Subscribe for future entities

        @callback
        def create_unifi_entity(
            description: UnifiEntityDescription, event: ItemEvent, obj_id: str
        ) -> None:
            """Create new UniFi entity on event."""
            if self._should_add_entity(description, obj_id):
                async_add_entities(
                    [unifi_platform_entity(obj_id, self.hub, description)]
                )

        for description in descriptions:
            description.api_handler_fn(self.hub.api).subscribe(
                partial(create_unifi_entity, description), ItemEvent.ADDED
            )
