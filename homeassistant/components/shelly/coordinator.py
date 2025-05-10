"""Coordinators for the Shelly integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from aioshelly.ble import async_ensure_ble_enabled, async_stop_scanner
from aioshelly.block_device import BlockDevice, BlockUpdateType
from aioshelly.const import GEN1, MODEL_VALVE
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    RpcCallError,
)
from aioshelly.rpc_device import RpcDevice, RpcUpdateType
from aioshelly.rpc_device.utils import bluetooth_mac_from_primary_mac
from propcache.api import cached_property

from homeassistant.components.bluetooth import async_remove_scanner
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bluetooth import async_connect_scanner
from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    ATTR_GENERATION,
    BATTERY_DEVICES_WITH_PERMANENT_CONNECTION,
    CONF_BLE_SCANNER_MODE,
    CONF_SLEEP_PERIOD,
    DOMAIN,
    DUAL_MODE_LIGHT_MODELS,
    ENTRY_RELOAD_COOLDOWN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_DICT,
    LOGGER,
    MAX_PUSH_UPDATE_FAILURES,
    MODELS_SUPPORTING_LIGHT_EFFECTS,
    OTA_BEGIN,
    OTA_ERROR,
    OTA_PROGRESS,
    OTA_SUCCESS,
    PUSH_UPDATE_ISSUE_ID,
    REST_SENSORS_UPDATE_INTERVAL,
    RPC_INPUTS_EVENTS_TYPES,
    RPC_RECONNECT_INTERVAL,
    RPC_SENSORS_POLLING_INTERVAL,
    SHBTN_MODELS,
    UPDATE_PERIOD_MULTIPLIER,
    BLEScannerMode,
)
from .utils import (
    async_create_issue_unsupported_firmware,
    get_block_device_sleep_period,
    get_device_entry_gen,
    get_host,
    get_http_port,
    get_rpc_device_wakeup_period,
    get_rpc_ws_url,
    get_shelly_model_name,
    update_device_fw_info,
)


@dataclass
class ShellyEntryData:
    """Class for sharing data within a given config entry."""

    platforms: list[Platform]
    block: ShellyBlockCoordinator | None = None
    rest: ShellyRestCoordinator | None = None
    rpc: ShellyRpcCoordinator | None = None
    rpc_poll: ShellyRpcPollingCoordinator | None = None
    rpc_script_events: dict[int, list[str]] | None = None
    rpc_supports_scripts: bool | None = None
    rpc_zigbee_enabled: bool | None = None


type ShellyConfigEntry = ConfigEntry[ShellyEntryData]


class ShellyCoordinatorBase[_DeviceT: BlockDevice | RpcDevice](
    DataUpdateCoordinator[None]
):
    """Coordinator for a Shelly device."""

    config_entry: ShellyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ShellyConfigEntry,
        device: _DeviceT,
        update_interval: float,
    ) -> None:
        """Initialize the Shelly device coordinator."""
        self.device = device
        self.device_id: str | None = None
        self._pending_platforms: list[Platform] | None = None
        device_name = device.name if device.initialized else entry.title
        interval_td = timedelta(seconds=update_interval)
        # The device has come online at least once. In the case of a sleeping RPC
        # device, this means that the device has connected to the WS server at least once.
        self._came_online_once = False
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=device_name,
            update_interval=interval_td,
        )

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
        return cast(str, self.config_entry.data[CONF_MODEL])

    @cached_property
    def mac(self) -> str:
        """Mac address of the device."""
        return cast(str, self.config_entry.unique_id)

    @property
    def sw_version(self) -> str:
        """Firmware version of the device."""
        return self.device.firmware_version if self.device.initialized else ""

    @property
    def sleep_period(self) -> int:
        """Sleep period of the device."""
        return self.config_entry.data.get(CONF_SLEEP_PERIOD, 0)

    def async_setup(self, pending_platforms: list[Platform] | None = None) -> None:
        """Set up the coordinator."""
        self._pending_platforms = pending_platforms
        dev_reg = dr.async_get(self.hass)
        if self.device.gen == GEN1:
            connections = {(CONNECTION_NETWORK_MAC, self.mac)}
        else:
            connections = {
                (CONNECTION_NETWORK_MAC, self.mac),
                (
                    CONNECTION_BLUETOOTH,
                    format_mac(bluetooth_mac_from_primary_mac(self.mac)),
                ),
            }
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            name=self.name,
            connections=connections,
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Shelly",
            model=get_shelly_model_name(self.model, self.sleep_period, self.device),
            model_id=self.model,
            sw_version=self.sw_version,
            hw_version=f"gen{get_device_entry_gen(self.config_entry)}",
            configuration_url=f"http://{get_host(self.config_entry.data[CONF_HOST])}:{get_http_port(self.config_entry.data)}",
        )
        self.device_id = device_entry.id

    async def shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.device.shutdown()

    async def _handle_ha_stop(self, _event: Event) -> None:
        """Handle Home Assistant stopping."""
        LOGGER.debug("Stopping RPC device coordinator for %s", self.name)
        await self.shutdown()

    async def _async_device_connect_task(self) -> bool:
        """Connect to a Shelly device task."""
        LOGGER.debug("Connecting to Shelly Device - %s", self.name)
        try:
            await self.device.initialize()
            update_device_fw_info(self.hass, self.device, self.config_entry)
        except (DeviceConnectionError, MacAddressMismatchError) as err:
            LOGGER.debug(
                "Error connecting to Shelly device %s, error: %r", self.name, err
            )
            return False
        except InvalidAuthError:
            self.config_entry.async_start_reauth(self.hass)
            return False

        if not self.device.firmware_supported:
            async_create_issue_unsupported_firmware(self.hass, self.config_entry)
            return False

        if not self._pending_platforms:
            return True

        LOGGER.debug("Device %s is online, resuming setup", self.name)
        platforms = self._pending_platforms
        self._pending_platforms = None

        data = {**self.config_entry.data}

        # Update sleep_period
        old_sleep_period = data[CONF_SLEEP_PERIOD]
        if isinstance(self.device, RpcDevice):
            new_sleep_period = get_rpc_device_wakeup_period(self.device.status)
        elif isinstance(self.device, BlockDevice):
            new_sleep_period = get_block_device_sleep_period(self.device.settings)

        if new_sleep_period != old_sleep_period:
            data[CONF_SLEEP_PERIOD] = new_sleep_period
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)

        # Resume platform setup
        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, platforms
        )

        return True

    async def _async_reload_entry(self) -> None:
        """Reload entry."""
        self._debounced_reload.async_cancel()
        LOGGER.debug("Reloading entry %s", self.name)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    async def async_shutdown_device_and_start_reauth(self) -> None:
        """Shutdown Shelly device and start reauth flow."""
        # not running disconnect events since we have auth error
        # and won't be able to send commands to the device
        self.last_update_success = False
        await self.shutdown()
        self.config_entry.async_start_reauth(self.hass)


class ShellyBlockCoordinator(ShellyCoordinatorBase[BlockDevice]):
    """Coordinator for a Shelly block based device."""

    def __init__(
        self, hass: HomeAssistant, entry: ShellyConfigEntry, device: BlockDevice
    ) -> None:
        """Initialize the Shelly block device coordinator."""
        if sleep_period := entry.data.get(CONF_SLEEP_PERIOD, 0):
            update_interval = UPDATE_PERIOD_MULTIPLIER * sleep_period
        else:
            update_interval = (
                UPDATE_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )
        super().__init__(hass, entry, device, update_interval)

        self._last_cfg_changed: int | None = None
        self._last_mode: str | None = None
        self._last_effect: str | None = None
        self._last_input_events_count: dict = {}
        self._last_target_temp: float | None = None
        self._push_update_failures: int = 0
        self._input_event_listeners: list[Callable[[dict[str, Any]], None]] = []

        entry.async_on_unload(
            self.async_add_listener(self._async_device_updates_handler)
        )

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
    def _async_device_updates_handler(self) -> None:
        """Handle device updates."""
        if not self.device.initialized:
            return

        # For buttons which are battery powered - set initial value for last_event_count
        if self.model in SHBTN_MODELS and self._last_input_events_count.get(1) is None:
            for block in self.device.blocks:
                if block.type != "device":
                    continue

                wakeup_event = cast(list, block.wakeupEvent)
                if len(wakeup_event) == 1 and wakeup_event[0] == "button":
                    self._last_input_events_count[1] = -1

                break

        # Check for input events and config change
        cfg_changed = 0
        for block in self.device.blocks:
            if block.type == "device" and block.cfgChanged is not None:
                cfg_changed = cast(int, block.cfgChanged)

            # Shelly TRV sends information about changing the configuration for no
            # reason, reloading the config entry is not needed for it.
            if self.model == MODEL_VALVE:
                self._last_cfg_changed = None

            # For dual mode bulbs ignore change if it is due to mode/effect change
            if self.model in DUAL_MODE_LIGHT_MODELS:
                if "mode" in block.sensor_ids:
                    if self._last_mode != block.mode:
                        self._last_cfg_changed = None
                    self._last_mode = block.mode

            if self.model in MODELS_SUPPORTING_LIGHT_EFFECTS:
                if "effect" in block.sensor_ids:
                    if self._last_effect != block.effect:
                        self._last_cfg_changed = None
                    self._last_effect = block.effect

            if (
                "inputEvent" not in block.sensor_ids
                or "inputEventCnt" not in block.sensor_ids
            ):
                LOGGER.debug("Skipping non-input event block %s", block.description)
                continue

            channel = int(block.channel or 0) + 1
            event_type = block.inputEvent
            last_event_count = self._last_input_events_count.get(channel)
            self._last_input_events_count[channel] = block.inputEventCnt

            if (
                last_event_count is None
                or last_event_count == block.inputEventCnt
                or event_type == ""
            ):
                LOGGER.debug("Skipping block event %s", event_type)
                continue

            if event_type in INPUTS_EVENTS_DICT:
                for event_callback in self._input_event_listeners:
                    event_callback(
                        {"channel": channel, "event": INPUTS_EVENTS_DICT[event_type]}
                    )
                self.hass.bus.async_fire(
                    EVENT_SHELLY_CLICK,
                    {
                        ATTR_DEVICE_ID: self.device_id,
                        ATTR_DEVICE: self.device.settings["device"]["hostname"],
                        ATTR_CHANNEL: channel,
                        ATTR_CLICK_TYPE: INPUTS_EVENTS_DICT[event_type],
                        ATTR_GENERATION: 1,
                    },
                )

        if self._last_cfg_changed is not None and cfg_changed > self._last_cfg_changed:
            LOGGER.info(
                "Config for %s changed, reloading entry in %s seconds",
                self.name,
                ENTRY_RELOAD_COOLDOWN,
            )
            self._debounced_reload.async_schedule_call()
        self._last_cfg_changed = cfg_changed

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if self.sleep_period:
            # Sleeping device, no point polling it, just mark it unavailable
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error_sleeping_device",
                translation_placeholders={
                    "device": self.name,
                    "period": str(self.sleep_period),
                },
            )

        LOGGER.debug("Polling Shelly Block Device - %s", self.name)
        try:
            await self.device.update()
        except DeviceConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"device": self.name},
            ) from err
        except InvalidAuthError:
            await self.async_shutdown_device_and_start_reauth()

    @callback
    def _async_handle_update(
        self, device_: BlockDevice, update_type: BlockUpdateType
    ) -> None:
        """Handle device update."""
        LOGGER.debug("Shelly %s handle update, type: %s", self.name, update_type)
        if update_type is BlockUpdateType.ONLINE:
            self._came_online_once = True
            self.config_entry.async_create_background_task(
                self.hass,
                self._async_device_connect_task(),
                "block device online",
                eager_start=True,
            )
        elif update_type is BlockUpdateType.COAP_PERIODIC:
            if self._push_update_failures >= MAX_PUSH_UPDATE_FAILURES:
                ir.async_delete_issue(
                    self.hass,
                    DOMAIN,
                    PUSH_UPDATE_ISSUE_ID.format(unique=self.mac),
                )
            self._push_update_failures = 0
        elif update_type is BlockUpdateType.COAP_REPLY:
            self._push_update_failures += 1
            if self._push_update_failures == MAX_PUSH_UPDATE_FAILURES:
                LOGGER.debug(
                    "Creating issue %s", PUSH_UPDATE_ISSUE_ID.format(unique=self.mac)
                )
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    PUSH_UPDATE_ISSUE_ID.format(unique=self.mac),
                    is_fixable=False,
                    is_persistent=False,
                    severity=ir.IssueSeverity.ERROR,
                    learn_more_url="https://www.home-assistant.io/integrations/shelly/#shelly-device-configuration-generation-1",
                    translation_key="push_update_failure",
                    translation_placeholders={
                        "device_name": self.config_entry.title,
                        "ip_address": self.device.ip_address,
                    },
                )
        if self._push_update_failures:
            LOGGER.debug(
                "Push update failures for %s: %s", self.name, self._push_update_failures
            )
        self.async_set_updated_data(None)

    def async_setup(self, pending_platforms: list[Platform] | None = None) -> None:
        """Set up the coordinator."""
        super().async_setup(pending_platforms)
        self.device.subscribe_updates(self._async_handle_update)


class ShellyRestCoordinator(ShellyCoordinatorBase[BlockDevice]):
    """Coordinator for a Shelly REST device."""

    def __init__(
        self, hass: HomeAssistant, device: BlockDevice, entry: ShellyConfigEntry
    ) -> None:
        """Initialize the Shelly REST device coordinator."""
        update_interval = REST_SENSORS_UPDATE_INTERVAL
        if (
            device.settings["device"]["type"]
            in BATTERY_DEVICES_WITH_PERMANENT_CONNECTION
        ):
            update_interval = (
                UPDATE_PERIOD_MULTIPLIER * device.settings["coiot"]["update_period"]
            )
        super().__init__(hass, entry, device, update_interval)

    async def _async_update_data(self) -> None:
        """Fetch data."""
        LOGGER.debug("REST update for %s", self.name)
        try:
            await self.device.update_status()

            if self.device.status["uptime"] > 2 * REST_SENSORS_UPDATE_INTERVAL:
                return
            await self.device.update_shelly()
        except (DeviceConnectionError, MacAddressMismatchError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"device": self.name},
            ) from err
        except InvalidAuthError:
            await self.async_shutdown_device_and_start_reauth()
        else:
            update_device_fw_info(self.hass, self.device, self.config_entry)


class ShellyRpcCoordinator(ShellyCoordinatorBase[RpcDevice]):
    """Coordinator for a Shelly RPC based device."""

    def __init__(
        self, hass: HomeAssistant, entry: ShellyConfigEntry, device: RpcDevice
    ) -> None:
        """Initialize the Shelly RPC device coordinator."""
        if sleep_period := entry.data.get(CONF_SLEEP_PERIOD, 0):
            update_interval = UPDATE_PERIOD_MULTIPLIER * sleep_period
        else:
            update_interval = RPC_RECONNECT_INTERVAL
        super().__init__(hass, entry, device, update_interval)

        self.connected = False
        self._disconnected_callbacks: list[CALLBACK_TYPE] = []
        self._connection_lock = asyncio.Lock()
        self._event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._ota_event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._input_event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._connect_task: asyncio.Task | None = None
        entry.async_on_unload(entry.add_update_listener(self._async_update_listener))

    @cached_property
    def bluetooth_source(self) -> str:
        """Return the Bluetooth source address.

        This is the Bluetooth MAC address of the device that is used
        for the Bluetooth scanner.
        """
        return format_mac(bluetooth_mac_from_primary_mac(self.mac)).upper()

    async def async_device_online(self, source: str) -> None:
        """Handle device going online."""
        if not self.sleep_period:
            await self.async_request_refresh()
        elif not self._came_online_once or not self.device.initialized:
            LOGGER.debug(
                "Sleepy device %s is online (source: %s), trying to poll and configure",
                self.name,
                source,
            )
            # Source told us the device is online, try to poll
            # the device and if possible, set up the outbound
            # websocket so the device will send us updates
            # instead of relying on polling it fast enough before
            # it goes to sleep again
            self._async_handle_rpc_device_online()

    def update_sleep_period(self) -> bool:
        """Check device sleep period & update if changed."""
        if (
            not self.device.initialized
            or not (wakeup_period := get_rpc_device_wakeup_period(self.device.status))
            or wakeup_period == self.sleep_period
        ):
            return False

        data = {**self.config_entry.data}
        data[CONF_SLEEP_PERIOD] = wakeup_period
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)

        update_interval = UPDATE_PERIOD_MULTIPLIER * wakeup_period
        self.update_interval = timedelta(seconds=update_interval)

        return True

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
    def async_subscribe_events(
        self, event_callback: Callable[[dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to events."""

        def _unsubscribe() -> None:
            self._event_listeners.remove(event_callback)

        self._event_listeners.append(event_callback)

        return _unsubscribe

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ShellyConfigEntry
    ) -> None:
        """Reconfigure on update."""
        async with self._connection_lock:
            if self.connected:
                self._async_run_disconnected_events()
                await self._async_run_connected_events()

    @callback
    def _async_device_event_handler(self, event_data: dict[str, Any]) -> None:
        """Handle device events."""
        events: list[dict[str, Any]] = event_data["events"]
        for event in events:
            event_type = event.get("event")
            if event_type is None:
                continue

            for event_callback in self._event_listeners:
                event_callback(event)

            if event_type in ("component_added", "component_removed", "config_changed"):
                self.update_sleep_period()
                LOGGER.info(
                    "Config for %s changed, reloading entry in %s seconds",
                    self.name,
                    ENTRY_RELOAD_COOLDOWN,
                )
                self._debounced_reload.async_schedule_call()
            elif event_type in RPC_INPUTS_EVENTS_TYPES:
                for event_callback in self._input_event_listeners:
                    event_callback(event)
                self.hass.bus.async_fire(
                    EVENT_SHELLY_CLICK,
                    {
                        ATTR_DEVICE_ID: self.device_id,
                        ATTR_DEVICE: self.device.hostname,
                        ATTR_CHANNEL: event["id"] + 1,
                        ATTR_CLICK_TYPE: event["event"],
                        ATTR_GENERATION: 2,
                    },
                )
            elif event_type in (OTA_BEGIN, OTA_ERROR, OTA_PROGRESS, OTA_SUCCESS):
                for event_callback in self._ota_event_listeners:
                    event_callback(event)

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if self.update_sleep_period() or self.hass.is_stopping:
            return

        if self.sleep_period:
            # Sleeping device, no point polling it, just mark it unavailable
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error_sleeping_device",
                translation_placeholders={
                    "device": self.name,
                    "period": str(self.sleep_period),
                },
            )

        async with self._connection_lock:
            if self.device.connected:  # Already connected
                return

            if not await self._async_device_connect_task():
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_error_reconnect_error",
                    translation_placeholders={"device": self.name},
                )

    async def _async_disconnected(self, reconnect: bool) -> None:
        """Handle device disconnected."""
        async with self._connection_lock:
            if not self.connected:  # Already disconnected
                return
            self.connected = False
            # Sleeping devices send data and disconnect
            # There are no disconnect events for sleeping devices
            # but we do need to make sure self.connected is False
            if self.sleep_period:
                return
            self._async_run_disconnected_events()
        # Try to reconnect right away if triggered by disconnect event
        if reconnect:
            await self.async_request_refresh()

    @callback
    def _async_run_disconnected_events(self) -> None:
        """Run disconnected events.

        This will be executed on disconnect or when the config entry
        is updated.
        """
        for disconnected_callback in self._disconnected_callbacks:
            disconnected_callback()
        self._disconnected_callbacks.clear()

    async def _async_connected(self) -> None:
        """Handle device connected."""
        async with self._connection_lock:
            if self.connected:  # Already connected
                return
            self.connected = True
            try:
                await self._async_run_connected_events()
            except DeviceConnectionError as err:
                LOGGER.error(
                    "Error running connected events for device %s: %s", self.name, err
                )
                self.last_update_success = False

    async def _async_run_connected_events(self) -> None:
        """Run connected events.

        This will be executed on connect or when the config entry
        is updated.
        """
        if not self.sleep_period:
            if (
                self.config_entry.runtime_data.rpc_supports_scripts
                and not self.config_entry.runtime_data.rpc_zigbee_enabled
            ):
                await self._async_connect_ble_scanner()
        else:
            await self._async_setup_outbound_websocket()

    async def _async_setup_outbound_websocket(self) -> None:
        """Set up outbound websocket if it is not enabled."""
        config = self.device.config
        if (
            (ws_config := config.get("ws"))
            and (not ws_config["server"] or not ws_config["enable"])
            and (ws_url := get_rpc_ws_url(self.hass))
        ):
            LOGGER.debug(
                "Setting up outbound websocket for device %s - %s", self.name, ws_url
            )
            await self.device.update_outbound_websocket(ws_url)

    async def _async_connect_ble_scanner(self) -> None:
        """Connect BLE scanner."""
        ble_scanner_mode = self.config_entry.options.get(
            CONF_BLE_SCANNER_MODE, BLEScannerMode.DISABLED
        )
        if ble_scanner_mode == BLEScannerMode.DISABLED and self.connected:
            await async_stop_scanner(self.device)
            async_remove_scanner(self.hass, self.bluetooth_source)
            return
        if await async_ensure_ble_enabled(self.device):
            # BLE enable required a reboot, don't bother connecting
            # the scanner since it will be disconnected anyway
            return
        assert self.device_id is not None
        self._disconnected_callbacks.append(
            await async_connect_scanner(
                self.hass, self, ble_scanner_mode, self.device_id
            )
        )

    @callback
    def _async_handle_rpc_device_online(self) -> None:
        """Handle device going online."""
        if self.device.connected or (
            self._connect_task and not self._connect_task.done()
        ):
            LOGGER.debug("Device %s already connected/connecting", self.name)
            return
        self._connect_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_device_connect_task(),
            "rpc device online",
            eager_start=True,
        )

    @callback
    def _async_handle_update(
        self, device_: RpcDevice, update_type: RpcUpdateType
    ) -> None:
        """Handle device update."""
        LOGGER.debug("Shelly %s handle update, type: %s", self.name, update_type)
        if update_type is RpcUpdateType.ONLINE:
            self._came_online_once = True
            self._async_handle_rpc_device_online()
        elif update_type is RpcUpdateType.INITIALIZED:
            self.config_entry.async_create_background_task(
                self.hass, self._async_connected(), "rpc device init", eager_start=True
            )
            # Make sure entities are marked available
            self.async_set_updated_data(None)
        elif update_type is RpcUpdateType.DISCONNECTED:
            self.config_entry.async_create_background_task(
                self.hass,
                self._async_disconnected(True),
                "rpc device disconnected",
                eager_start=True,
            )
            # Make sure entities are marked as unavailable
            self.async_set_updated_data(None)
        elif update_type is RpcUpdateType.STATUS:
            self.async_set_updated_data(None)
            if self.sleep_period:
                update_device_fw_info(self.hass, self.device, self.config_entry)
        elif update_type is RpcUpdateType.EVENT and (event := self.device.event):
            self._async_device_event_handler(event)

    def async_setup(self, pending_platforms: list[Platform] | None = None) -> None:
        """Set up the coordinator."""
        super().async_setup(pending_platforms)
        self.device.subscribe_updates(self._async_handle_update)
        if self.device.initialized:
            # If we are already initialized, we are connected
            self.config_entry.async_create_task(
                self.hass, self._async_connected(), eager_start=True
            )

    async def shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self.device.connected:
            try:
                if not self.sleep_period:
                    await async_stop_scanner(self.device)
                await super().shutdown()
            except InvalidAuthError:
                self.config_entry.async_start_reauth(self.hass)
                return
            except DeviceConnectionError as err:
                # If the device is restarting or has gone offline before
                # the ping/pong timeout happens, the shutdown command
                # will fail, but we don't care since we are unloading
                # and if we setup again, we will fix anything that is
                # in an inconsistent state at that time.
                LOGGER.debug("Error during shutdown for device %s: %s", self.name, err)
                return
        await self._async_disconnected(False)


class ShellyRpcPollingCoordinator(ShellyCoordinatorBase[RpcDevice]):
    """Polling coordinator for a Shelly RPC based device."""

    def __init__(
        self, hass: HomeAssistant, entry: ShellyConfigEntry, device: RpcDevice
    ) -> None:
        """Initialize the RPC polling coordinator."""
        super().__init__(hass, entry, device, RPC_SENSORS_POLLING_INTERVAL)

    async def _async_update_data(self) -> None:
        """Fetch data."""
        if not self.device.connected:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error_device_disconnected",
                translation_placeholders={"device": self.name},
            )

        LOGGER.debug("Polling Shelly RPC Device - %s", self.name)
        try:
            await self.device.poll()
        except (DeviceConnectionError, RpcCallError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"device": self.name},
            ) from err
        except InvalidAuthError:
            await self.async_shutdown_device_and_start_reauth()


def get_block_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> ShellyBlockCoordinator | None:
    """Get a Shelly block device coordinator for the given device id."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            entry = hass.config_entries.async_get_entry(config_entry)
            if (
                entry
                and entry.state is ConfigEntryState.LOADED
                and hasattr(entry, "runtime_data")
                and isinstance(entry.runtime_data, ShellyEntryData)
                and (coordinator := entry.runtime_data.block)
            ):
                return coordinator

    return None


def get_rpc_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> ShellyRpcCoordinator | None:
    """Get a Shelly RPC device coordinator for the given device id."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get(device_id):
        for config_entry in device.config_entries:
            entry = hass.config_entries.async_get_entry(config_entry)
            if (
                entry
                and entry.state is ConfigEntryState.LOADED
                and hasattr(entry, "runtime_data")
                and isinstance(entry.runtime_data, ShellyEntryData)
                and (coordinator := entry.runtime_data.rpc)
            ):
                return coordinator

    return None


async def async_reconnect_soon(hass: HomeAssistant, entry: ShellyConfigEntry) -> None:
    """Try to reconnect soon."""
    if (
        not hass.is_stopping
        and entry.state is ConfigEntryState.LOADED
        and (coordinator := entry.runtime_data.rpc)
    ):
        entry.async_create_background_task(
            hass,
            coordinator.async_device_online("zeroconf"),
            "reconnect soon",
            eager_start=True,
        )
