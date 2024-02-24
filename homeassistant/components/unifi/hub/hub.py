"""UniFi Network abstraction."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from functools import partial

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.models.device import DeviceSetPoePortModeRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.event import async_call_later, async_track_time_interval
import homeassistant.util.dt as dt_util

from ..const import (
    ATTR_MANUFACTURER,
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_ALLOW_UPTIME_SENSORS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_DPI_RESTRICTIONS,
    DEFAULT_IGNORE_WIRED_BUG,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_DEVICES,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
    PLATFORMS,
    UNIFI_WIRELESS_CLIENTS,
)
from ..entity import UnifiEntity, UnifiEntityDescription
from .websocket import UnifiWebsocket

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiHub:
    """Manages a single UniFi Network instance."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: aiounifi.Controller
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self.websocket = UnifiWebsocket(hass, api, self.signal_reachable)

        self.wireless_clients = hass.data[UNIFI_WIRELESS_CLIENTS]

        self.site = config_entry.data[CONF_SITE_ID]
        self.is_admin = False

        self._cancel_heartbeat_check: CALLBACK_TYPE | None = None
        self._heartbeat_time: dict[str, datetime] = {}

        self.load_config_entry_options()

        self.entities: dict[str, str] = {}
        self.known_objects: set[tuple[str, str]] = set()

        self.poe_command_queue: dict[str, dict[int, str]] = {}
        self._cancel_poe_command: CALLBACK_TYPE | None = None

    def load_config_entry_options(self) -> None:
        """Store attributes to avoid property call overhead since they are called frequently."""
        options = self.config_entry.options

        # Allow creating entities from clients.
        self.option_supported_clients: list[str] = options.get(CONF_CLIENT_SOURCE, [])

        # Device tracker options

        # Config entry option to not track clients.
        self.option_track_clients = options.get(
            CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS
        )
        # Config entry option to not track wired clients.
        self.option_track_wired_clients = options.get(
            CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
        )
        # Config entry option to not track devices.
        self.option_track_devices: bool = options.get(
            CONF_TRACK_DEVICES, DEFAULT_TRACK_DEVICES
        )
        # Config entry option listing what SSIDs are being used to track clients.
        self.option_ssid_filter = set(options.get(CONF_SSID_FILTER, []))
        # Config entry option defining number of seconds from last seen to away
        self.option_detection_time = timedelta(
            seconds=options.get(CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME)
        )
        # Config entry option to ignore wired bug.
        self.option_ignore_wired_bug = options.get(
            CONF_IGNORE_WIRED_BUG, DEFAULT_IGNORE_WIRED_BUG
        )

        # Client control options

        # Config entry option with list of clients to control network access.
        self.option_block_clients: list[str] = options.get(CONF_BLOCK_CLIENT, [])
        # Config entry option to control DPI restriction groups.
        self.option_dpi_restrictions: bool = options.get(
            CONF_DPI_RESTRICTIONS, DEFAULT_DPI_RESTRICTIONS
        )

        # Statistics sensor options

        # Config entry option to allow bandwidth sensors.
        self.option_allow_bandwidth_sensors: bool = options.get(
            CONF_ALLOW_BANDWIDTH_SENSORS, DEFAULT_ALLOW_BANDWIDTH_SENSORS
        )
        # Config entry option to allow uptime sensors.
        self.option_allow_uptime_sensors: bool = options.get(
            CONF_ALLOW_UPTIME_SENSORS, DEFAULT_ALLOW_UPTIME_SENSORS
        )

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        host: str = self.config_entry.data[CONF_HOST]
        return host

    @property
    def available(self) -> bool:
        """Websocket connection state."""
        return self.websocket.available

    @callback
    @staticmethod
    def register_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
        entity_class: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        requires_admin: bool = False,
    ) -> None:
        """Register platform for UniFi entity management."""
        hub: UnifiHub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
        if requires_admin and not hub.is_admin:
            return
        hub.register_platform_add_entities(
            entity_class, descriptions, async_add_entities
        )

    @callback
    def _async_should_add_entity(
        self, description: UnifiEntityDescription, obj_id: str
    ) -> bool:
        """Check if entity should be added."""
        return bool(
            (description.key, obj_id) not in self.known_objects
            and description.allowed_fn(self, obj_id)
            and description.supported_fn(self, obj_id)
        )

    @callback
    def register_platform_add_entities(
        self,
        unifi_platform_entity: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Subscribe to UniFi API handlers and create entities."""

        @callback
        def async_load_entities(descriptions: Iterable[UnifiEntityDescription]) -> None:
            """Load and subscribe to UniFi endpoints."""

            @callback
            def async_add_unifi_entities() -> None:
                """Add UniFi entity."""
                async_add_entities(
                    [
                        unifi_platform_entity(obj_id, self, description)
                        for description in descriptions
                        for obj_id in description.api_handler_fn(self.api)
                        if self._async_should_add_entity(description, obj_id)
                    ]
                )

            async_add_unifi_entities()

            @callback
            def async_create_entity(
                description: UnifiEntityDescription, event: ItemEvent, obj_id: str
            ) -> None:
                """Create new UniFi entity on event."""
                if self._async_should_add_entity(description, obj_id):
                    async_add_entities(
                        [unifi_platform_entity(obj_id, self, description)]
                    )

            for description in descriptions:
                description.api_handler_fn(self.api).subscribe(
                    partial(async_create_entity, description), ItemEvent.ADDED
                )

            self.config_entry.async_on_unload(
                async_dispatcher_connect(
                    self.hass,
                    self.signal_options_update,
                    async_add_unifi_entities,
                )
            )

        async_load_entities(descriptions)

    @property
    def signal_reachable(self) -> str:
        """Integration specific event to signal a change in connection status."""
        return f"unifi-reachable-{self.config_entry.entry_id}"

    @property
    def signal_options_update(self) -> str:
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{self.config_entry.entry_id}"

    @property
    def signal_heartbeat_missed(self) -> str:
        """Event specific per UniFi device tracker to signal new heartbeat missed."""
        return "unifi-heartbeat-missed"

    async def initialize(self) -> None:
        """Set up a UniFi Network instance."""
        await self.api.initialize()

        assert self.config_entry.unique_id is not None
        self.is_admin = self.api.sites[self.config_entry.unique_id].role == "admin"

        # Restore device tracker clients that are not a part of active clients list.
        macs: list[str] = []
        entity_registry = er.async_get(self.hass)
        for entry in async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        ):
            if entry.domain == Platform.DEVICE_TRACKER and "-" in entry.unique_id:
                macs.append(entry.unique_id.split("-", 1)[1])

        for mac in self.option_supported_clients + self.option_block_clients + macs:
            if mac not in self.api.clients and mac in self.api.clients_all:
                self.api.clients.process_raw([dict(self.api.clients_all[mac].raw)])

        self.wireless_clients.update_clients(set(self.api.clients.values()))

        self.config_entry.add_update_listener(self.async_config_entry_updated)

        self._cancel_heartbeat_check = async_track_time_interval(
            self.hass, self._async_check_for_stale, CHECK_HEARTBEAT_INTERVAL
        )

    @callback
    def async_heartbeat(
        self, unique_id: str, heartbeat_expire_time: datetime | None = None
    ) -> None:
        """Signal when a device has fresh home state."""
        if heartbeat_expire_time is not None:
            self._heartbeat_time[unique_id] = heartbeat_expire_time
            return

        if unique_id in self._heartbeat_time:
            del self._heartbeat_time[unique_id]

    @callback
    def _async_check_for_stale(self, *_: datetime) -> None:
        """Check for any devices scheduled to be marked disconnected."""
        now = dt_util.utcnow()

        unique_ids_to_remove = []
        for unique_id, heartbeat_expire_time in self._heartbeat_time.items():
            if now > heartbeat_expire_time:
                async_dispatcher_send(
                    self.hass, f"{self.signal_heartbeat_missed}_{unique_id}"
                )
                unique_ids_to_remove.append(unique_id)

        for unique_id in unique_ids_to_remove:
            del self._heartbeat_time[unique_id]

    @callback
    def async_queue_poe_port_command(
        self, device_id: str, port_idx: int, poe_mode: str
    ) -> None:
        """Queue commands to execute them together per device."""
        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

        device_queue = self.poe_command_queue.setdefault(device_id, {})
        device_queue[port_idx] = poe_mode

        async def async_execute_command(now: datetime) -> None:
            """Execute previously queued commands."""
            queue = self.poe_command_queue.copy()
            self.poe_command_queue.clear()
            for device_id, device_commands in queue.items():
                device = self.api.devices[device_id]
                commands = list(device_commands.items())
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_poe_command = async_call_later(self.hass, 5, async_execute_command)

    @property
    def device_info(self) -> DeviceInfo:
        """UniFi Network device info."""
        assert self.config_entry.unique_id is not None

        version: str | None = None
        if sysinfo := next(iter(self.api.system_information.values()), None):
            version = sysinfo.version

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(UNIFI_DOMAIN, self.config_entry.unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model="UniFi Network Application",
            name="UniFi Network",
            sw_version=version,
        )

    @callback
    def async_update_device_registry(self) -> DeviceEntry:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id, **self.device_info
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        If config entry is updated due to reauth flow
        the entry might already have been reset and thus is not available.
        """
        if not (hub := hass.data[UNIFI_DOMAIN].get(config_entry.entry_id)):
            return
        hub.load_config_entry_options()
        async_dispatcher_send(hass, hub.signal_options_update)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to unifi.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.websocket.stop()

    async def async_reset(self) -> bool:
        """Reset this hub to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        await self.websocket.stop_and_wait()

        unload_ok = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        if not unload_ok:
            return False

        if self._cancel_heartbeat_check:
            self._cancel_heartbeat_check()
            self._cancel_heartbeat_check = None

        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

        return True
