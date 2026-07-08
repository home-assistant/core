"""Coordinator for Easywave integration with automatic USB reconnect."""

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

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    EVENT_EASYWAVE,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
)
from .gateway_device import update_gateway_device
from .transceiver import RX11Transceiver

if TYPE_CHECKING:
    from . import EasywaveConfigEntry

_LOGGER = logging.getLogger(__name__)


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

    def _update_gateway_device(self) -> None:
        """Update the gateway device in the device registry."""
        update_gateway_device(self.hass, self.config_entry, self.transceiver)

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
            else:
                _LOGGER.warning(
                    "RX11 device not found, entering offline mode. "
                    "Entities will be unavailable until device connects"
                )
        except (OSError, TimeoutError) as err:
            raise UpdateFailed(f"Setup failed: {err}") from err

    def _register_transceiver_callbacks(self) -> None:
        """Register connection lifecycle callbacks on the transceiver."""
        self.transceiver.set_disconnect_callback(self._on_transceiver_disconnect)
        self.transceiver.set_connected_callback(self._on_transceiver_connected)

    @callback
    def _on_transceiver_connected(self) -> None:
        """Update the gateway device registry when the transceiver connects."""
        self._update_gateway_device()

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

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data periodically.

        This is called every DEVICE_SCAN_INTERVAL to:
        - Check connection status
        - Attempt reconnection if offline
        - Detect disconnections of previously connected devices
        """
        try:
            # If offline, attempt reconnect
            if self.is_offline:
                connected = await self.transceiver.reconnect()
                if connected:
                    self.is_offline = False
                    self._register_transceiver_callbacks()
                    self._update_gateway_device()
                    # Restart telegram listener if any entities need it
                    if self._has_telegram_listeners:
                        self._start_telegram_listener()
                    # Return new device state; coordinator will notify listeners
                    return {
                        "is_connected": self.transceiver.is_connected,
                        "device_path": self.transceiver.device_path,
                    }
                # Still offline, no need to log as error — offline mode is expected
                return {
                    "is_connected": False,
                    "device_path": None,
                }
            # Verify transceiver still reports connected
            # (disconnect callback handles immediate detection,
            # this is a safety net for edge cases)
            if not self.transceiver.is_connected:
                _LOGGER.warning("Connection lost, entering offline mode")
                self.is_offline = True
                self._stop_telegram_listener()
                return {
                    "is_connected": False,
                    "device_path": None,
                }
        except UpdateFailed:
            if not self.is_offline:
                self.is_offline = True
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

    @property
    def _has_telegram_listeners(self) -> bool:
        """Return True if any entities need telegram listening."""
        return bool(self._transmitter_entities or self._sensor_entities)

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
        """Start the telegram listener when entities are registered."""
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
        if self._listener_task is current_task:
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
        """Dispatch a button push event to matching entities."""
        serial_hex = event.transmitter_serial.hex()
        is_low_battery = event.function == ButtonFunction.LOW_BATTERY
        matched_device_id: str | None = None

        for entity in list(self._transmitter_entities):
            if _serial_hex_matches(event.transmitter_serial, entity.transmitter_serial):
                entity.handle_telegram(event)
                entity.handle_battery_status(is_low_battery)
                matched_device_id = entity.device_id
        if matched_device_id is None:
            _LOGGER.debug("Received EW push from unknown transmitter: %s", serial_hex)
            return
        if event.function == ButtonFunction.LOW_BATTERY:
            return
        button_letter = "abcd"[event.button] if event.button < 4 else None
        if button_letter is not None:
            self.fire_device_event(
                matched_device_id,
                EVENT_TYPE_BUTTON_PRESS,
                subtype=button_letter,
            )

    @callback
    def _dispatch_button_release(self, event: ButtonReleaseEvent) -> None:
        """Dispatch a button release event to matching entities."""
        matched_device_id: str | None = None
        for entity in list(self._transmitter_entities):
            if _serial_hex_matches(event.transmitter_serial, entity.transmitter_serial):
                entity.handle_telegram(event)
                matched_device_id = entity.device_id
        if matched_device_id is not None:
            self.fire_device_event(
                matched_device_id,
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
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, easywave_device_id)}
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
