"""Coordinators for the Refoss RPC integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from aiorefoss.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    RpcCallError,
)
from aiorefoss.rpc_device import RpcDevice, RpcUpdateType
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    ENTRY_RELOAD_COOLDOWN,
    EVENT_REFOSS_CLICK,
    INPUTS_EVENTS_TYPES,
    LOGGER,
    OTA_BEGIN,
    OTA_ERROR,
    OTA_PROGRESS,
    OTA_SUCCESS,
    REFOSS_CHECK_INTERVAL,
)
from .utils import get_host, update_device_fw_info


@dataclass
class RefossEntryData:
    """Class for sharing data within a given config entry."""

    platforms: list[Platform]
    coordinator: RefossCoordinator | None = None


RefossConfigEntry = ConfigEntry[RefossEntryData]


class RefossCoordinatorBase(DataUpdateCoordinator[None]):
    """Coordinator for a Refoss device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RefossConfigEntry,
        device: RpcDevice,
        update_interval: float,
    ) -> None:
        """Initialize the Refoss device coordinator."""
        self.entry = entry
        self.device = device
        self.device_id: str
        device_name = device.name if device.initialized else entry.title
        interval_td = timedelta(seconds=update_interval)
        self._came_online_once = False
        super().__init__(hass, LOGGER, name=device_name, update_interval=interval_td)

        self._debounced_reload: Debouncer[Coroutine[Any, Any, None]] = Debouncer(
            hass,
            LOGGER,
            cooldown=ENTRY_RELOAD_COOLDOWN,
            immediate=False,
            function=self._async_reload_entry,
        )
        entry.async_on_unload(self._debounced_reload.async_shutdown)

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)
        )

    @cached_property
    def model(self) -> str:
        """Model of the device."""
        return cast(str, self.entry.data["model"])

    @cached_property
    def mac(self) -> str:
        """Mac address of the device."""
        return cast(str, self.entry.unique_id)

    @property
    def sw_version(self) -> str:
        """Firmware version of the device."""
        return self.device.firmware_version if self.device.initialized else ""

    @property
    def hw_version(self) -> str:
        """Hardware version of the device."""
        return self.device.hw_version if self.device.initialized else ""

    def async_setup(self) -> None:
        """Set up the coordinator."""
        dev_reg = dr.async_get(self.hass)
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self.device.name,
            connections={(CONNECTION_NETWORK_MAC, self.mac)},
            manufacturer="Refoss",
            model=self.model,
            sw_version=self.sw_version,
            hw_version=self.hw_version,
            configuration_url=f"http://{get_host(self.entry.data[CONF_HOST])}",
        )
        self.device_id = device_entry.id
        self.remove_old_entity()

    def remove_old_entity(self) -> None:
        """Remove old entity when reload."""
        entity_reg = er.async_get(self.hass)
        entities = er.async_entries_for_device(
            registry=entity_reg, device_id=self.device_id
        )
        for entity in entities:
            LOGGER.debug("Removing old entity: %s", entity.entity_id)
            entity_reg.async_remove(entity.entity_id)

    async def shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.device.shutdown()

    async def _handle_ha_stop(self, _event: Event) -> None:
        """Handle Home Assistant stopping."""
        LOGGER.debug("Stopping  device coordinator for %s", self.name)
        await self.shutdown()

    async def _async_device_connect_task(self) -> bool:
        """Connect to a Refoss device task."""
        LOGGER.debug("Connecting to Refoss Device - %s", self.name)
        try:
            await self.device.initialize()
            update_device_fw_info(self.hass, self.device, self.entry)
        except (DeviceConnectionError, MacAddressMismatchError) as err:
            LOGGER.debug(
                "Error connecting to Refoss device %s, error: %r", self.name, err
            )
            return False
        except InvalidAuthError:
            self.entry.async_start_reauth(self.hass)
            return False

        return True

    async def _async_reload_entry(self) -> None:
        """Reload entry."""
        self._debounced_reload.async_cancel()
        LOGGER.debug("Reloading entry %s", self.name)
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_shutdown_device_and_start_reauth(self) -> None:
        """Shutdown Refoss device and start reauth flow."""
        self.last_update_success = False
        await self.shutdown()
        self.entry.async_start_reauth(self.hass)


class RefossCoordinator(RefossCoordinatorBase):
    """Coordinator for a Refoss  device."""

    def __init__(
        self, hass: HomeAssistant, entry: RefossConfigEntry, device: RpcDevice
    ) -> None:
        """Initialize the Refoss coordinator."""
        self.entry = entry
        super().__init__(hass, entry, device, REFOSS_CHECK_INTERVAL)

        self.connected = False
        self._connection_lock = asyncio.Lock()
        self._ota_event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._input_event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._connect_task: asyncio.Task | None = None

    async def async_device_online(self, source: str) -> None:
        """Handle device going online."""

        if not self._came_online_once or not self.device.initialized:
            LOGGER.debug(
                "device %s is online (source: %s), trying to poll and configure",
                self.name,
                source,
            )
            self._async_handle_refoss_device_online()

    @callback
    def async_subscribe_ota_events(
        self, ota_event_callback: Callable[[dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to OTA events."""

        def _unsubscribe() -> None:
            self._ota_event_listeners.remove(ota_event_callback)

        self._ota_event_listeners.append(ota_event_callback)

        return _unsubscribe

    @callback
    def async_subscribe_input_events(
        self, input_event_callback: Callable[[dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to input events."""

        def _unsubscribe() -> None:
            self._input_event_listeners.remove(input_event_callback)

        self._input_event_listeners.append(input_event_callback)

        return _unsubscribe

    @callback
    def _async_device_event_handler(self, event_data: dict[str, Any]) -> None:
        """Handle device events."""
        events: list[dict[str, Any]] = event_data["events"]
        for event in events:
            event_type = event.get("event")
            if event_type is None:
                continue

            RELOAD_EVENTS = {"config_changed", "emmerge_change", "cfg_change"}
            if event_type in RELOAD_EVENTS:
                LOGGER.info(
                    "Config for %s changed, reloading entry in %s seconds",
                    self.name,
                    ENTRY_RELOAD_COOLDOWN,
                )
                self._debounced_reload.async_schedule_call()
            elif event_type in INPUTS_EVENTS_TYPES:
                for event_callback in self._input_event_listeners:
                    event_callback(event)
                self.hass.bus.async_fire(
                    EVENT_REFOSS_CLICK,
                    {
                        ATTR_DEVICE_ID: self.device_id,
                        ATTR_DEVICE: self.device.name,
                        ATTR_CHANNEL: event["id"],
                        ATTR_CLICK_TYPE: event["event"],
                    },
                )
            elif event_type in (OTA_BEGIN, OTA_ERROR, OTA_PROGRESS, OTA_SUCCESS):
                for event_callback in self._ota_event_listeners:
                    event_callback(event)

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if self.hass.is_stopping:
            return

        async with self._connection_lock:
            if not self.device.connected:
                if not await self._async_device_connect_task():
                    raise UpdateFailed("Device reconnect error")
                return
        try:
            LOGGER.debug("Polling Refoss  Device - %s", self.name)
            await self.device.poll()
        except DeviceConnectionError as err:
            raise UpdateFailed(f"Device disconnected: {err!r}") from err
        except RpcCallError as err:
            raise UpdateFailed(f"RPC call failed: {err!r}") from err
        except InvalidAuthError:
            await self.async_shutdown_device_and_start_reauth()
            return

    async def _async_disconnected(self, reconnect: bool) -> None:
        """Handle device disconnected."""
        async with self._connection_lock:
            if not self.connected:  # Already disconnected
                return
            self.connected = False

        # Try to reconnect right away if triggered by disconnect event
        if reconnect:
            await self.async_request_refresh()

    async def _async_connected(self) -> None:
        """Handle device connected."""
        async with self._connection_lock:
            if self.connected:  # Already connected
                return
            self.connected = True

    @callback
    def _async_handle_refoss_device_online(self) -> None:
        """Handle device going online."""
        if self.device.connected or (
            self._connect_task and not self._connect_task.done()
        ):
            LOGGER.debug("Device %s already connected/connecting", self.name)
            return
        self._connect_task = self.entry.async_create_background_task(
            self.hass,
            self._async_device_connect_task(),
            "device online",
            eager_start=True,
        )

    @callback
    def _async_handle_update(
        self, device: RpcDevice, update_type: RpcUpdateType
    ) -> None:
        """Handle device update."""
        LOGGER.debug("Refoss %s handle update, type: %s", self.name, update_type)
        if update_type is RpcUpdateType.ONLINE:
            self._came_online_once = True
            self._async_handle_refoss_device_online()
        elif update_type is RpcUpdateType.INITIALIZED:
            self.entry.async_create_background_task(
                self.hass, self._async_connected(), "device init", eager_start=True
            )
            self.async_set_updated_data(None)
        elif update_type is RpcUpdateType.DISCONNECTED:
            self.entry.async_create_background_task(
                self.hass,
                self._async_disconnected(True),
                "device disconnected",
                eager_start=True,
            )
            self.async_set_updated_data(None)
        elif update_type is RpcUpdateType.STATUS:
            self.async_set_updated_data(None)

        elif update_type is RpcUpdateType.EVENT and (event := self.device.event):
            self._async_device_event_handler(event)

    def async_setup(self) -> None:
        """Set up the coordinator."""
        super().async_setup()
        self.device.subscribe_updates(self._async_handle_update)
        if self.device.initialized:
            # If we are already initialized, we are connected
            self.entry.async_create_task(
                self.hass, self._async_connected(), eager_start=True
            )

    async def shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self.device.connected:
            try:
                await super().shutdown()
            except InvalidAuthError:
                self.entry.async_start_reauth(self.hass)
                return
            except DeviceConnectionError as err:
                LOGGER.debug("Error during shutdown for device %s: %s", self.name, err)
                return
        await self._async_disconnected(False)


def get_refoss_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> RefossCoordinator | None:
    """Get a Refoss  device coordinator for the given device id."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            entry = hass.config_entries.async_get_entry(config_entry)
            if (
                entry
                and entry.state is ConfigEntryState.LOADED
                and hasattr(entry, "runtime_data")
                and isinstance(entry.runtime_data, RefossEntryData)
                and (coordinator := entry.runtime_data.coordinator)
            ):
                return coordinator

    return None


async def async_reconnect_soon(hass: HomeAssistant, entry: RefossConfigEntry) -> None:
    """Try to reconnect soon."""
    if (
        not hass.is_stopping
        and entry.state is ConfigEntryState.LOADED
        and (coordinator := entry.runtime_data.coordinator)
    ):
        entry.async_create_background_task(
            hass,
            coordinator.async_device_online("zeroconf"),
            "reconnect soon",
            eager_start=True,
        )
