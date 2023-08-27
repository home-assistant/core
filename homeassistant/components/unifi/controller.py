"""UniFi Network abstraction."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import ssl
from types import MappingProxyType
from typing import Any

from aiohttp import CookieJar
import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.models.configuration import Configuration
from aiounifi.models.device import DeviceSetPoePortModeRequest
from aiounifi.websocket import WebsocketState

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_MANUFACTURER,
    BLOCK_SWITCH,
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
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
    LOGGER,
    PLATFORMS,
    UNIFI_WIRELESS_CLIENTS,
)
from .entity import UnifiEntity, UnifiEntityDescription
from .errors import AuthenticationRequired, CannotConnect

RETRY_TIMER = 15
CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UniFiController:
    """Manages a single UniFi Network instance."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: aiounifi.Controller
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api

        api.ws_state_callback = self.async_unifi_ws_state_callback

        self.available = True
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
        self.option_block_clients = options.get(CONF_BLOCK_CLIENT, [])
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
        """Return the host of this controller."""
        host: str = self.config_entry.data[CONF_HOST]
        return host

    @property
    def mac(self) -> str | None:
        """Return the mac address of this controller."""
        for client in self.api.clients.values():
            if self.host == client.ip:
                return client.mac
        return None

    @callback
    def register_platform_add_entities(
        self,
        unifi_platform_entity: type[UnifiEntity],
        descriptions: tuple[UnifiEntityDescription, ...],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Subscribe to UniFi API handlers and create entities."""

        @callback
        def async_load_entities(description: UnifiEntityDescription) -> None:
            """Load and subscribe to UniFi endpoints."""
            api_handler = description.api_handler_fn(self.api)

            @callback
            def async_add_unifi_entity(obj_ids: list[str]) -> None:
                """Add UniFi entity."""
                async_add_entities(
                    [
                        unifi_platform_entity(obj_id, self, description)
                        for obj_id in obj_ids
                        if (description.key, obj_id) not in self.known_objects
                        if description.allowed_fn(self, obj_id)
                        if description.supported_fn(self, obj_id)
                    ]
                )

            async_add_unifi_entity(list(api_handler))

            @callback
            def async_create_entity(event: ItemEvent, obj_id: str) -> None:
                """Create new UniFi entity on event."""
                async_add_unifi_entity([obj_id])

            api_handler.subscribe(async_create_entity, ItemEvent.ADDED)

            @callback
            def async_options_updated() -> None:
                """Load new entities based on changed options."""
                async_add_unifi_entity(list(api_handler))

            self.config_entry.async_on_unload(
                async_dispatcher_connect(
                    self.hass, self.signal_options_update, async_options_updated
                )
            )

        for description in descriptions:
            async_load_entities(description)

    @callback
    def async_unifi_ws_state_callback(self, state: WebsocketState) -> None:
        """Handle messages back from UniFi library."""
        if state == WebsocketState.DISCONNECTED and self.available:
            LOGGER.warning("Lost connection to UniFi Network")

        if (state == WebsocketState.RUNNING and not self.available) or (
            state == WebsocketState.DISCONNECTED and self.available
        ):
            self.available = state == WebsocketState.RUNNING
            async_dispatcher_send(self.hass, self.signal_reachable)

            if not self.available:
                self.hass.loop.call_later(RETRY_TIMER, self.reconnect, True)
            else:
                LOGGER.info("Connected to UniFi Network")

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

        # Restore clients that are not a part of active clients list.
        entity_registry = er.async_get(self.hass)
        for entry in async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        ):
            if entry.domain == Platform.DEVICE_TRACKER:
                mac = entry.unique_id.split("-", 1)[0]
            elif entry.domain == Platform.SWITCH and entry.unique_id.startswith(
                BLOCK_SWITCH
            ):
                mac = entry.unique_id.split("-", 1)[1]
            else:
                continue

            if mac in self.api.clients or mac not in self.api.clients_all:
                continue

            client = self.api.clients_all[mac]
            self.api.clients.process_raw([dict(client.raw)])
            LOGGER.debug(
                "Restore disconnected client %s (%s)",
                entry.entity_id,
                client.mac,
            )

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

        async def async_execute_poe_port_command(now: datetime) -> None:
            """Execute previously queued commands."""
            queue = self.poe_command_queue.copy()
            self.poe_command_queue.clear()
            for device_id, device_commands in queue.items():
                device = self.api.devices[device_id]
                commands = [(idx, mode) for idx, mode in device_commands.items()]
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_poe_command = async_track_point_in_utc_time(
            self.hass,
            async_execute_poe_port_command,
            dt_util.utcnow() + timedelta(seconds=5),
        )

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        if self.mac is None:
            return

        device_registry = dr.async_get(self.hass)

        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.mac)},
            default_manufacturer=ATTR_MANUFACTURER,
            default_model="UniFi Network",
            default_name="UniFi Network",
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        If config entry is updated due to reauth flow
        the entry might already have been reset and thus is not available.
        """
        if not (controller := hass.data[UNIFI_DOMAIN].get(config_entry.entry_id)):
            return
        controller.load_config_entry_options()
        async_dispatcher_send(hass, controller.signal_options_update)

    @callback
    def reconnect(self, log: bool = False) -> None:
        """Prepare to reconnect UniFi session."""
        if log:
            LOGGER.info("Will try to reconnect to UniFi Network")
        self.hass.loop.create_task(self.async_reconnect())

    async def async_reconnect(self) -> None:
        """Try to reconnect UniFi Network session."""
        try:
            async with asyncio.timeout(5):
                await self.api.login()
                self.api.start_websocket()

        except (
            asyncio.TimeoutError,
            aiounifi.BadGateway,
            aiounifi.ServiceUnavailable,
            aiounifi.AiounifiException,
        ):
            self.hass.loop.call_later(RETRY_TIMER, self.reconnect)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to unifi.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.stop_websocket()

    async def async_reset(self) -> bool:
        """Reset this controller to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        self.api.stop_websocket()

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


async def get_unifi_controller(
    hass: HomeAssistant,
    config: MappingProxyType[str, Any],
) -> aiounifi.Controller:
    """Create a controller object and verify authentication."""
    ssl_context: ssl.SSLContext | bool = False

    if verify_ssl := config.get(CONF_VERIFY_SSL):
        session = aiohttp_client.async_get_clientsession(hass)
        if isinstance(verify_ssl, str):
            ssl_context = ssl.create_default_context(cafile=verify_ssl)
    else:
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )

    controller = aiounifi.Controller(
        Configuration(
            session,
            host=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
            site=config[CONF_SITE_ID],
            ssl_context=ssl_context,
        )
    )

    try:
        async with asyncio.timeout(10):
            await controller.login()
        return controller

    except aiounifi.Unauthorized as err:
        LOGGER.warning(
            "Connected to UniFi Network at %s but not registered: %s",
            config[CONF_HOST],
            err,
        )
        raise AuthenticationRequired from err

    except (
        asyncio.TimeoutError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.RequestError,
        aiounifi.ResponseError,
    ) as err:
        LOGGER.error(
            "Error connecting to the UniFi Network at %s: %s", config[CONF_HOST], err
        )
        raise CannotConnect from err

    except aiounifi.LoginRequired as err:
        LOGGER.warning(
            "Connected to UniFi Network at %s but login required: %s",
            config[CONF_HOST],
            err,
        )
        raise AuthenticationRequired from err

    except aiounifi.AiounifiException as err:
        LOGGER.exception("Unknown UniFi Network communication error occurred: %s", err)
        raise AuthenticationRequired from err
