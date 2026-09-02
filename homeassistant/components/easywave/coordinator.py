"""Coordinator for Easywave integration."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, override

from easywave_home_control.codec import (
    ButtonFunction,
    ButtonPushEvent,
    ButtonReleaseEvent,
    EwbRcvEvent,
    SensorMeasurementPayload,
    SensorTelegramEvent,
)
from easywave_home_control.codec.sensors import SensorLearnPayload

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ENTRY_TYPE,
    CONF_TRANSMITTER_SERIAL,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
)
from .devices import get_devices
from .entity import EasywaveDeviceEntry
from .gateway_device import update_gateway_device
from .transceiver import RX11Transceiver

if TYPE_CHECKING:
    from . import EasywaveConfigEntry

_LOGGER = logging.getLogger(__name__)

_BATTERY_STATE_OK = "ok"
_BATTERY_STATE_LOW = "low"
_BATTERY_CLEAR_THRESHOLD = 2


def _serial_hex_matches(device_serial: bytes, configured_serial: str) -> bool:
    """Return True when a telegram serial matches configured device data."""
    return device_serial.hex().lower() == configured_serial.lower()


class EasywaveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Easywave integration."""

    config_entry: EasywaveConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        transceiver: RX11Transceiver,
        config_entry: EasywaveConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEVICE_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.transceiver = transceiver
        self.is_offline = not transceiver.is_connected
        self._transmitter_entities: list[Any] = []
        self._sensor_entities: list[Any] = []
        self._listener_task: asyncio.Task[None] | None = None
        self._learning_lock = asyncio.Lock()
        self._ha_started = self.hass.state is CoreState.running
        self._gateway_last_status = "disconnected"
        self._battery_ok_streak: dict[str, int] = {}
        self._battery_state: dict[str, str] = {}
        self._register_homeassistant_started_listener()

    def is_learning_busy(self) -> bool:
        """Return True when a device learning session holds the hardware lock."""
        return self._learning_lock.locked()

    async def begin_learning(self) -> bool:
        """Try to acquire exclusive access for a device learning session."""
        if self._learning_lock.locked():
            return False
        await self._learning_lock.acquire()
        return True

    def end_learning(self) -> None:
        """Release a device learning session lock."""
        self._learning_lock.release()

    def _update_gateway_device(self) -> None:
        """Update the gateway device in the device registry."""
        update_gateway_device(self.hass, self.config_entry, self.transceiver)

    def _register_homeassistant_started_listener(self) -> None:
        """Track when Home Assistant has started for device automation events."""
        if self._ha_started:
            self._gateway_last_status = self._gateway_connection_status()
            return

        @callback
        def _on_ha_started(_event: Any) -> None:
            self._ha_started = True
            self._gateway_last_status = self._gateway_connection_status()

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)
        )

    def _gateway_connection_status(self) -> str:
        """Return the gateway connection status key."""
        if self.is_offline:
            return "disconnected"
        if self.transceiver.is_connected:
            return "connected"
        return "disconnected"

    @callback
    def _sync_gateway_connection_events(self) -> None:
        """Fire gateway device automation events on connection transitions."""
        if not self._ha_started:
            return
        new_status = self._gateway_connection_status()
        if new_status == self._gateway_last_status:
            return
        old_status = self._gateway_last_status
        _LOGGER.debug("Gateway status: %s -> %s", old_status, new_status)
        self._gateway_last_status = new_status
        if new_status == "connected":
            self.fire_device_event(
                self.config_entry.entry_id,
                EVENT_TYPE_GATEWAY_CONNECTED,
                subtype="connected",
            )
        elif new_status == "disconnected":
            self.fire_device_event(
                self.config_entry.entry_id,
                EVENT_TYPE_GATEWAY_DISCONNECTED,
                subtype="disconnected",
            )

    @override
    async def _async_setup(self) -> None:
        """Set up coordinator and attempt initial connection.

        Called by DataUpdateCoordinator before the first update.
        Raises UpdateFailed if initialization fails completely.
        """
        try:
            connected = await self.transceiver.connect()
            self.is_offline = not connected

            if connected:
                self._register_transceiver_callbacks()
                self._update_gateway_device()
                self.ensure_telegram_listener()
            else:
                raise UpdateFailed(
                    "RX11 device not found, setup deferred until device connects"
                )
        except (OSError, TimeoutError) as err:
            raise UpdateFailed(f"Setup failed: {err}") from err

    def _register_transceiver_callbacks(self) -> None:
        """Register connection lifecycle callbacks on the transceiver."""
        self.transceiver.set_disconnect_callback(self._on_transceiver_disconnect)
        self.transceiver.set_connected_callback(self._on_transceiver_connected)

    @callback
    def _on_transceiver_connected(self) -> None:
        """Handle a successful transceiver connection from the library."""
        was_offline = self.is_offline
        self.is_offline = False
        self._update_gateway_device()
        if self._has_telegram_listeners:
            self._start_telegram_listener()
        self.async_set_updated_data(
            {
                "is_connected": self.transceiver.is_connected,
                "device_path": self.transceiver.device_path,
            }
        )
        if was_offline:
            self._sync_gateway_connection_events()

    @callback
    def _on_transceiver_disconnect(self) -> None:
        """Called from transceiver when connection is lost.

        May be invoked from the event loop (health-check / RxModule
        disconnect handler), so use call_soon_threadsafe to guarantee
        thread safety regardless of the calling context.
        """
        self.hass.loop.call_soon_threadsafe(self._handle_disconnect)

    @callback
    def _handle_disconnect(self) -> None:
        """Mark offline and push updated data to listeners immediately."""
        if self.is_offline:
            return
        _LOGGER.warning("Lost connection to RX11, entering offline mode")
        self.is_offline = True
        self._stop_telegram_listener()
        self.async_set_updated_data(
            {
                "is_connected": False,
                "device_path": None,
            }
        )
        self._sync_gateway_connection_events()

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data periodically.

        Attempt reconnection when offline and detect disconnections the
        callback may miss.
        """
        try:
            if self.is_offline:
                connected = await self.transceiver.reconnect()
                if connected:
                    self.is_offline = False
                    self._register_transceiver_callbacks()
                    self._update_gateway_device()
                    if self._has_telegram_listeners:
                        self._start_telegram_listener()
                    self._sync_gateway_connection_events()
                    return {
                        "is_connected": self.transceiver.is_connected,
                        "device_path": self.transceiver.device_path,
                    }
                return {
                    "is_connected": False,
                    "device_path": None,
                }
            if not self.transceiver.is_connected:
                _LOGGER.warning("Connection lost, entering offline mode")
                self.is_offline = True
                self._stop_telegram_listener()
                self._sync_gateway_connection_events()
                return {
                    "is_connected": False,
                    "device_path": None,
                }
        except UpdateFailed:
            raise
        except (OSError, TimeoutError) as err:
            _LOGGER.warning("Error updating coordinator data: %s", err)
            self.is_offline = True
            raise UpdateFailed(f"Update failed: {err}") from err
        else:
            return {
                "is_connected": self.transceiver.is_connected,
                "device_path": self.transceiver.device_path,
            }

    @override
    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect transceiver."""
        try:
            task = self._stop_telegram_listener()
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await self.transceiver.dispose()
            _LOGGER.debug("Coordinator shutdown complete")
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Error during coordinator shutdown: %s", err)
        finally:
            await super().async_shutdown()

    def _configured_transmitters(self) -> list[EasywaveDeviceEntry]:
        """Return transmitters configured on the gateway entry."""
        return [
            device
            for device in get_devices(self.config_entry)
            if device.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TRANSMITTER
        ]

    def _transmitter_device_id_for_serial(self, serial: bytes) -> str | None:
        """Return the configured transmitter device id for a telegram serial."""
        for device in self._configured_transmitters():
            if _serial_hex_matches(serial, device.data[CONF_TRANSMITTER_SERIAL]):
                return device.device_id
        return None

    @callback
    def _handle_transmitter_battery_status(self, device_id: str, is_low: bool) -> None:
        """Fire battery device automation events for a configured transmitter."""
        if is_low:
            self._battery_ok_streak[device_id] = 0
            if self._battery_state.get(device_id) != _BATTERY_STATE_LOW:
                self._battery_state[device_id] = _BATTERY_STATE_LOW
                self.fire_device_event(device_id, EVENT_TYPE_BATTERY_LOW, subtype="low")
            return
        if self._battery_state.get(device_id) == _BATTERY_STATE_OK:
            return
        self._battery_ok_streak[device_id] = (
            self._battery_ok_streak.get(device_id, 0) + 1
        )
        if self._battery_ok_streak[device_id] >= _BATTERY_CLEAR_THRESHOLD:
            self._battery_state[device_id] = _BATTERY_STATE_OK
            self._battery_ok_streak[device_id] = 0
            self.fire_device_event(device_id, EVENT_TYPE_BATTERY_NORMAL, subtype="ok")

    @property
    def _has_telegram_listeners(self) -> bool:
        """Return True when runtime telegram reception is required."""
        return bool(
            self._transmitter_entities
            or self._sensor_entities
            or self._configured_transmitters()
        )

    def register_transmitter_entities(self, entities: list[Any]) -> None:
        """Register transmitter event entities for telegram dispatching."""
        self._transmitter_entities.extend(entities)
        if entities:
            self.ensure_telegram_listener()

    def unregister_transmitter_entity(self, entity: Any) -> None:
        """Remove a single transmitter entity from telegram dispatching."""
        with contextlib.suppress(ValueError):
            self._transmitter_entities.remove(entity)
        if not self._has_telegram_listeners:
            self._stop_telegram_listener()

    def register_sensor_entities(self, entities: list[Any]) -> None:
        """Register neo sensor entities for telegram dispatching."""
        self._sensor_entities.extend(entities)
        if entities:
            self.ensure_telegram_listener()

    def unregister_sensor_entity(self, entity: Any) -> None:
        """Remove a single neo sensor entity from telegram dispatching."""
        with contextlib.suppress(ValueError):
            self._sensor_entities.remove(entity)
        if not self._has_telegram_listeners:
            self._stop_telegram_listener()

    def ensure_telegram_listener(self) -> None:
        """Start the telegram listener when reception is required."""
        if self._has_telegram_listeners and not self.is_offline:
            self._start_telegram_listener()

    def _start_telegram_listener(self) -> None:
        """Start the background telegram listener task."""
        if self._listener_task is not None and not self._listener_task.done():
            return
        if not self._has_telegram_listeners or self.is_offline:
            return
        self._listener_task = self.config_entry.async_create_background_task(
            self.hass,
            self._telegram_listener_loop(),
            "easywave_telegram_listener",
        )

    def _stop_telegram_listener(self) -> asyncio.Task[None] | None:
        """Cancel the listener and return the task so callers can await it."""
        if self._listener_task is None:
            return None
        task = self._listener_task
        self._listener_task = None
        if not task.done():
            task.cancel()
        return task

    async def _clear_listener_task(self) -> None:
        """Clear the listener task reference after the loop exits."""
        current_task = asyncio.current_task()
        if self._listener_task is not None and self._listener_task is not current_task:
            return
        self._listener_task = None

    async def suspend_telegram_listener(self) -> None:
        """Pause the telegram listener so a learning task has exclusive hardware access.

        Stops the listener task and cancels any EWB_RCV that was in-flight on the
        hardware, leaving a clean slate for the learning loop.
        """
        task = self._stop_telegram_listener()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.transceiver.cancel_pending_receives()

    def resume_telegram_listener(self) -> None:
        """Restart the telegram listener after a learning task completes."""
        if self._has_telegram_listeners and not self.is_offline:
            self._start_telegram_listener()

    async def _telegram_listener_loop(self) -> None:
        """Continuously listen for all EW/EWneo telegrams and dispatch."""
        try:
            while not self.is_offline and self._has_telegram_listeners:
                try:
                    telegram = await self.transceiver.receive_telegram(timeout=30.0)
                    if telegram is None:
                        continue
                    self._dispatch_telegram(telegram)
                except asyncio.CancelledError:
                    break
                except (OSError, TimeoutError) as err:
                    _LOGGER.debug("Telegram listener error: %s", err)
                    await asyncio.sleep(5.0)
                except Exception:
                    _LOGGER.exception("Unexpected error in telegram listener")
                    await asyncio.sleep(1.0)
        finally:
            await self._clear_listener_task()

    @callback
    def _dispatch_telegram(self, event: EwbRcvEvent) -> None:
        """Dispatch a received telegram to the matching entity."""
        if isinstance(event, ButtonPushEvent):
            if not event.should_ignore:
                self._dispatch_button_push(event)
        elif isinstance(event, ButtonReleaseEvent):
            self._dispatch_button_release(event)
        elif isinstance(event, SensorTelegramEvent):
            self._dispatch_sensor_telegram(event)
        else:
            _LOGGER.debug("Unhandled telegram event type: %s", type(event).__name__)

    @callback
    def _dispatch_button_push(self, event: ButtonPushEvent) -> None:
        """Dispatch a button push event to matching entities and automations."""
        serial_hex = event.transmitter_serial.hex()
        is_low_battery = event.function == ButtonFunction.LOW_BATTERY
        device_id = self._transmitter_device_id_for_serial(event.transmitter_serial)

        for entity in list(self._transmitter_entities):
            if _serial_hex_matches(event.transmitter_serial, entity.transmitter_serial):
                if not is_low_battery:
                    entity.handle_telegram(event)
                entity.handle_battery_status(is_low_battery)

        if device_id is None:
            _LOGGER.debug("Received EW push from unknown transmitter: %s", serial_hex)
            return
        if is_low_battery:
            self._handle_transmitter_battery_status(device_id, True)
            return
        self._handle_transmitter_battery_status(device_id, False)
        button_letter = "abcd"[event.button] if event.button < 4 else None
        if button_letter is not None:
            self.fire_device_event(
                device_id,
                EVENT_TYPE_BUTTON_PRESS,
                subtype=button_letter,
            )

    @callback
    def _dispatch_button_release(self, event: ButtonReleaseEvent) -> None:
        """Dispatch a button release event to matching entities and automations."""
        device_id = self._transmitter_device_id_for_serial(event.transmitter_serial)
        for entity in list(self._transmitter_entities):
            if _serial_hex_matches(event.transmitter_serial, entity.transmitter_serial):
                entity.handle_telegram(event)
        if device_id is not None:
            self.fire_device_event(
                device_id,
                EVENT_TYPE_BUTTON_RELEASE,
                subtype="released",
            )

    @callback
    def _dispatch_sensor_telegram(self, event: SensorTelegramEvent) -> None:
        """Dispatch a neo sensor measurement to matching entities."""
        serial_hex = event.sensor_serial.hex()
        if isinstance(event.payload, SensorLearnPayload):
            _LOGGER.debug(
                "Received EWneo learn telegram from %s at runtime",
                serial_hex,
            )
            return
        if not isinstance(event.payload, SensorMeasurementPayload):
            _LOGGER.debug(
                "Received EWneo telegram from %s with unsupported payload type %s",
                serial_hex,
                type(event.payload).__name__,
            )
            return
        if event.payload.should_ignore:
            return

        matched = False
        for entity in list(self._sensor_entities):
            if _serial_hex_matches(event.sensor_serial, entity.sensor_serial):
                entity.handle_telegram(event)
                matched = True
        if not matched:
            configured = sorted(
                {entity.sensor_serial.lower() for entity in self._sensor_entities}
            )
            _LOGGER.debug(
                "Received EWneo measurement from unknown sensor %s "
                "(configured sensors: %s)",
                serial_hex,
                ", ".join(configured) if configured else "none",
            )

    def fire_device_event(
        self,
        easywave_device_id: str,
        event_type: str,
        **event_data: Any,
    ) -> None:
        """Fire a homeassistant event for device automations."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, easywave_device_id),
            self.config_entry.entry_id,
        )
        if device_entry is None:
            return
        self.hass.bus.async_fire(
            EVENT_EASYWAVE,
            {
                "device_id": device_entry.id,
                "type": event_type,
                **event_data,
            },
        )
