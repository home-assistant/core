"""UniFi Network entity loader.

Central point to load entities for the different platforms.
Make sure expected clients are available for platforms.
"""

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.models.client import Client

from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import CLIENT_RESTORE_MAX_AGE, LOGGER, UNIFI_WIRELESS_CLIENTS
from ..coordinator import UnifiDataUpdateCoordinator
from ..entity import UnifiEntity, UnifiEntityDescription

if TYPE_CHECKING:
    from .hub import UnifiHub

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiEntityLoader:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(self, hub: UnifiHub) -> None:
        """Initialize the UniFi entity loader."""
        self.hub = hub
        self.api_updaters = (
            hub.api.clients.update,
            hub.api.clients_all.update,
            hub.api.devices.update,
            hub.api.dpi_apps.update,
            hub.api.dpi_groups.update,
            hub.api.port_forwarding.update,
            hub.api.sites.update,
            hub.api.system_information.update,
            hub.api.firewall_policies.update,
            hub.api.wlans.update,
        )
        self.wireless_clients = hub.hass.data[UNIFI_WIRELESS_CLIENTS]

        self._polling_coordinators: dict[int, UnifiDataUpdateCoordinator] = {
            id(hub.api.traffic_rules): UnifiDataUpdateCoordinator(
                hub, hub.api.traffic_rules
            ),
            id(hub.api.traffic_routes): UnifiDataUpdateCoordinator(
                hub, hub.api.traffic_routes
            ),
        }
        for coordinator in self._polling_coordinators.values():
            coordinator.async_add_listener(lambda: None)

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

    async def initialize(self) -> None:
        """Initialize API data and extra client support."""
        await asyncio.gather(
            self._refresh_api_data(),
            self._refresh_data(
                [
                    coordinator.async_refresh
                    for coordinator in self._polling_coordinators.values()
                ]
            ),
        )
        self._restore_inactive_clients()
        self.wireless_clients.update_clients(set(self.hub.api.clients.values()))

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

    async def _refresh_api_data(self) -> None:
        """Refresh API data from network application."""
        await self._refresh_data(self.api_updaters)

    @callback
    def _restore_inactive_clients(self) -> None:
        """Restore recently seen inactive clients and prune stale ones.

        The UniFi controller keeps a record of every client it has ever seen.
        Restoring all of them on every startup is what makes installations pile
        up thousands of stale client devices. Only clients seen within the
        retention window, or explicitly selected or blocked, are restored.
        Trackers falling outside that window are removed together with their
        device so the registry stops growing unbounded.
        """
        config = self.hub.config
        api = self.hub.api
        entity_registry = er.async_get(self.hub.hass)
        device_registry = dr.async_get(self.hub.hass)

        now = dt_util.utcnow()
        always_restore = set(config.option_supported_clients)
        always_restore.update(config.option_block_clients)

        pruned = 0
        for entry in er.async_entries_for_config_entry(
            entity_registry, config.entry.entry_id
        ):
            if entry.domain != Platform.DEVICE_TRACKER or "-" not in entry.unique_id:
                continue

            mac = entry.unique_id.split("-", 1)[1]
            if mac in api.clients or mac in always_restore:
                continue

            client = api.clients_all.get(mac)
            if client is not None and not self._client_is_stale(client, now):
                api.clients.process_raw([dict(client.raw)])
                continue

            self._remove_client(entity_registry, device_registry, entry.entity_id, mac)
            pruned += 1

        if pruned:
            LOGGER.debug("Pruned %s stale UniFi client device(s)", pruned)

        for mac in always_restore:
            if mac not in api.clients and mac in api.clients_all:
                api.clients.process_raw([dict(api.clients_all[mac].raw)])

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
        """Remove a stale client's tracker entity and its device."""
        entity_registry.async_remove(entity_id)
        if device := device_registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)}
        ):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=self.hub.config.entry.entry_id
            )

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
    def get_data_update_coordinator(
        self, handler: APIHandler
    ) -> UnifiDataUpdateCoordinator | None:
        """Return the polling coordinator for a handler, if available."""
        return self._polling_coordinators.get(id(handler))

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
