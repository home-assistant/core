"""Coordinator for Flic Button integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from bleak import BleakError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEVICE_TYPE_MODEL_NAMES,
    DOMAIN,
    EVENT_TYPE_DUO_DIAL_CHANGED,
    EVENT_TYPE_SLOT_CHANGED,
    FLIC_BUTTON_EVENT,
    DeviceType,
)
from .flic_client import FlicClient, FlicProtocolError
from .handlers import DeviceCapabilities, DeviceProtocolHandler

_LOGGER = logging.getLogger(__name__)

SLOT_STORE_VERSION = 1
SLOT_SAVE_DELAY = 5  # seconds to debounce slot value saves

SIGNAL_BUTTON_EVENT = f"{DOMAIN}_button_event_{{0}}"
SIGNAL_ROTATE_EVENT = f"{DOMAIN}_rotate_event_{{0}}"
SIGNAL_SELECTOR_EVENT = f"{DOMAIN}_selector_event_{{0}}"
SIGNAL_SLOT_EVENT = f"{DOMAIN}_slot_{{mode}}_{{address}}"
SIGNAL_DUO_DIAL_EVENT = f"{DOMAIN}_duo_dial_{{button}}_{{address}}"


def format_event_dispatcher_name(address: str) -> str:
    """Format dispatcher signal name for button events."""
    return SIGNAL_BUTTON_EVENT.format(address.replace(":", "").lower())


def format_rotate_dispatcher_name(address: str) -> str:
    """Format dispatcher signal name for rotate events."""
    return SIGNAL_ROTATE_EVENT.format(address.replace(":", "").lower())


def format_selector_dispatcher_name(address: str) -> str:
    """Format dispatcher signal name for selector slot events."""
    return SIGNAL_SELECTOR_EVENT.format(address.replace(":", "").lower())


def format_duo_dial_dispatcher_name(address: str, button_index: int) -> str:
    """Format dispatcher signal name for Duo dial position events.

    Args:
        address: Bluetooth address of the device
        button_index: Button index (0=big, 1=small)

    Returns:
        Signal name for dispatcher

    """
    return SIGNAL_DUO_DIAL_EVENT.format(
        button=button_index, address=address.replace(":", "").lower()
    )


def format_slot_dispatcher_name(address: str, mode_index: int) -> str:
    """Format dispatcher signal name for slot position events.

    Args:
        address: Bluetooth address of the device
        mode_index: Twist mode index (0-11 for slots)

    Returns:
        Signal name for dispatcher

    """
    return SIGNAL_SLOT_EVENT.format(
        mode=mode_index, address=address.replace(":", "").lower()
    )


class FlicCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for managing Flic button connection and data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FlicClient,
        config_entry: ConfigEntry,
        serial_number: str | None = None,
        battery_level: int | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            client: Flic client instance
            config_entry: Config entry for this device
            serial_number: Button serial number (used to determine if Duo)
            battery_level: Battery level from pairing (0-1024)

        """
        # Disable polling - battery level is fetched on each connection via command
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.address}",
            update_interval=None,  # Disable polling
            config_entry=config_entry,
        )
        self.client = client
        self._serial_number = serial_number
        self._connected = False
        self._reconnect_lock = asyncio.Lock()
        self._battery_level = battery_level
        self._firmware_version: int | None = None

        # Slot value persistence (Twist devices)
        self._slot_values: dict[int, float] = {}
        self._slot_store: Store[dict[str, Any]] = Store(
            hass, SLOT_STORE_VERSION, f"{DOMAIN}.{config_entry.entry_id}.slots"
        )
        self._slot_save_unsub: CALLBACK_TYPE | None = None

        # Set up button event callback
        self.client.on_button_event = self._handle_button_event

        # Set up rotate event callback (for Flic Duo)
        self.client.on_rotate_event = self._handle_rotate_event

        # Set initial data with battery level from pairing
        if battery_level is not None:
            self.data = {"battery_voltage": self._raw_to_voltage(battery_level)}
        else:
            self.data = {}

    @property
    def handler(self) -> DeviceProtocolHandler:
        """Return the protocol handler."""
        return self.client.handler

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        return self.client.capabilities

    @property
    def is_duo(self) -> bool:
        """Return if connected button is a Flic Duo."""
        return self.device_type == DeviceType.DUO

    @property
    def is_twist(self) -> bool:
        """Return if connected button is a Flic Twist."""
        return self.device_type == DeviceType.TWIST

    @property
    def device_type(self) -> DeviceType:
        """Return the device type.

        Prioritizes client detection (protocol handler type), falling back
        to serial number prefix if client detection is unavailable.
        """
        if self.client.is_twist:
            return DeviceType.TWIST
        if self.client.is_duo:
            return DeviceType.DUO
        if self._serial_number:
            return DeviceType.from_serial_number(self._serial_number)
        return DeviceType.FLIC2

    @property
    def model_name(self) -> str:
        """Return model name based on button type."""
        return DEVICE_TYPE_MODEL_NAMES[self.device_type]

    @property
    def serial_number(self) -> str | None:
        """Return the button serial number."""
        return self._serial_number

    @property
    def connected(self) -> bool:
        """Return if the coordinator is connected to the button."""
        return self._connected

    def _raw_to_voltage(self, battery_level: int) -> float:
        """Convert raw battery level to voltage.

        Twist returns millivolts directly (2 AAA batteries).
        Flic 2/Duo return a 10-bit ADC value (0-1024, 3.6V reference).
        """
        if self.is_twist:
            return battery_level / 1000.0
        return battery_level * 3.6 / 1024.0

    @property
    def firmware_version(self) -> int | None:
        """Return the firmware version of the device."""
        return self._firmware_version

    @property
    def device_id(self) -> str | None:
        """Get device ID from registry."""
        if not self.config_entry:
            return None
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.client.address)}
        )
        return device.id if device else None

    async def async_load_slot_values(self) -> None:
        """Load persisted slot values from storage."""
        data = await self._slot_store.async_load()
        if data and "slots" in data:
            self._slot_values = {int(k): float(v) for k, v in data["slots"].items()}
            _LOGGER.debug(
                "Loaded %d persisted slot values for %s",
                len(self._slot_values),
                self.client.address,
            )

    def get_slot_value(self, mode_index: int) -> float:
        """Get the persisted value for a slot."""
        return self._slot_values.get(mode_index, 0.0)

    @callback
    def set_slot_value(self, mode_index: int, percentage: float) -> None:
        """Set and persist a slot value."""
        self._slot_values[mode_index] = percentage
        self._schedule_slot_save()

    @callback
    def _schedule_slot_save(self) -> None:
        """Schedule a debounced save of slot values."""
        if self._slot_save_unsub is not None:
            self._slot_save_unsub()
        self._slot_save_unsub = async_call_later(
            self.hass, SLOT_SAVE_DELAY, self._async_save_slot_values
        )

    async def _async_save_slot_values(self, _now: datetime | None = None) -> None:
        """Save slot values to storage."""
        self._slot_save_unsub = None
        await self._slot_store.async_save(
            {"slots": {str(k): v for k, v in self._slot_values.items()}}
        )

    async def _async_restore_slot_positions(self) -> None:
        """Restore persisted slot positions to the device after reconnect."""
        if not self.is_twist or not self._slot_values:
            return

        for mode_index, percentage in self._slot_values.items():
            if percentage == 0.0:
                continue
            try:
                await self.async_update_twist_position(mode_index, percentage)
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to restore slot %d position to %.1f%%",
                    mode_index,
                    percentage,
                )

    async def async_connect(self) -> None:
        """Connect to button and authenticate."""
        try:
            await self.client.connect()

            # Authenticate using stored credentials
            await self.client.quick_verify()

            # Initialize button events
            await self.client.init_button_events()

            # Request battery level (non-fatal on failure)
            try:
                battery_level = await self.client.get_battery_level()
                voltage = self._raw_to_voltage(battery_level)
                self.data = {"battery_voltage": voltage}
                _LOGGER.info(
                    "Battery level for %s: raw=%d, voltage=%.3fV",
                    self.client.address,
                    battery_level,
                    voltage,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to retrieve battery level from %s, using stored value",
                    self.client.address,
                )

            # Request firmware version (non-fatal on failure)
            try:
                self._firmware_version = await self.client.get_firmware_version()
                _LOGGER.debug(
                    "Firmware version for %s: %d",
                    self.client.address,
                    self._firmware_version,
                )
                device_registry = dr.async_get(self.hass)
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, self.client.address)}
                )
                if device:
                    device_registry.async_update_device(
                        device.id,
                        sw_version=str(self._firmware_version),
                    )
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to retrieve firmware version from %s",
                    self.client.address,
                )

            self._connected = True
            _LOGGER.info(
                "Successfully connected to Flic button %s", self.client.address
            )

            # Restore persisted slot positions to the device
            await self._async_restore_slot_positions()

        except (TimeoutError, BleakError, FlicProtocolError) as err:
            self._connected = False
            _LOGGER.error(
                "Failed to connect to Flic button %s: %s", self.client.address, err
            )
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from button."""
        # Cancel pending save timer and flush slot values to disk
        if self._slot_save_unsub is not None:
            self._slot_save_unsub()
            self._slot_save_unsub = None
        if self._slot_values:
            await self._async_save_slot_values()

        self._connected = False
        await self.client.disconnect()

    async def async_reconnect_if_needed(self) -> None:
        """Reconnect to button if disconnected."""
        async with self._reconnect_lock:
            if self.client.is_connected:
                return
            if self._connected:
                # Connection was lost, update state
                self._connected = False
                self.async_set_updated_data(self.data)
            try:
                _LOGGER.debug("Attempting to reconnect to %s", self.client.address)
                await self.async_connect()
                # Notify entities that connection is restored
                self.async_set_updated_data(self.data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Reconnection failed: %s", err)

    @callback
    def _handle_button_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle button event from client.

        Args:
            event_type: Type of event (up, down, click, double_click, hold)
            event_data: Event data dictionary

        """
        _LOGGER.debug(
            "Button event from %s: %s (data: %s)",
            self.client.address,
            event_type,
            event_data,
        )

        # Dispatch to event entities via signal
        async_dispatcher_send(
            self.hass,
            format_event_dispatcher_name(self.client.address),
            event_type,
            event_data,
        )

        # Fire Home Assistant event for automations
        self.hass.bus.async_fire(
            FLIC_BUTTON_EVENT,
            {
                "device_id": self.device_id,
                "address": self.client.address,
                "event_type": event_type,
                **event_data,
            },
        )

    @callback
    def _handle_rotate_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle rotate event from client.

        Args:
            event_type: Type of event (rotate_clockwise, rotate_counter_clockwise)
            event_data: Event data dictionary with rotation details

        """
        _LOGGER.debug(
            "Rotate event from %s: %s (data: %s)",
            self.client.address,
            event_type,
            event_data,
        )

        # Dispatch to event entities via signal
        async_dispatcher_send(
            self.hass,
            format_rotate_dispatcher_name(self.client.address),
            event_type,
            event_data,
        )

        # For Duo: dispatch dial position updates and fire event (per button)
        dial_percentage = event_data.get("dial_percentage")
        button_index = event_data.get("button_index")
        if dial_percentage is not None and button_index is not None and self.is_duo:
            _LOGGER.debug(
                "Duo dial position update (button %d): %.1f%%",
                button_index,
                dial_percentage,
            )
            async_dispatcher_send(
                self.hass,
                format_duo_dial_dispatcher_name(self.client.address, button_index),
                dial_percentage,
            )

            # Fire dial changed event for device triggers
            self.hass.bus.async_fire(
                FLIC_BUTTON_EVENT,
                {
                    "device_id": self.device_id,
                    "address": self.client.address,
                    "event_type": EVENT_TYPE_DUO_DIAL_CHANGED,
                    "button_index": button_index,
                    "position": dial_percentage,
                },
            )

        twist_mode_index = event_data.get("twist_mode_index")
        selector_index = event_data.get("selector_index")
        mode_percentage = event_data.get("mode_percentage")

        # For modes 0-11: update slot number entity with position percentage
        # Modes 0-11 are the 12 slots, mode 12 is the slot-changing mode
        if (
            twist_mode_index is not None
            and 0 <= twist_mode_index <= 11
            and mode_percentage is not None
        ):
            _LOGGER.debug(
                "Slot %d position update: %.1f%%", twist_mode_index, mode_percentage
            )
            self.set_slot_value(twist_mode_index, mode_percentage)
            async_dispatcher_send(
                self.hass,
                format_slot_dispatcher_name(self.client.address, twist_mode_index),
                mode_percentage,
            )

            # Fire slot changed event for device triggers
            self.hass.bus.async_fire(
                FLIC_BUTTON_EVENT,
                {
                    "device_id": self.device_id,
                    "address": self.client.address,
                    "event_type": EVENT_TYPE_SLOT_CHANGED[twist_mode_index],
                    "slot_index": twist_mode_index,
                    "position": mode_percentage,
                },
            )

        # For mode 12 (slot-changing): update selector entity with which slot is selected
        if twist_mode_index == 12 and selector_index is not None:
            _LOGGER.debug("Push-twist selector update: slot %d", selector_index)
            async_dispatcher_send(
                self.hass,
                format_selector_dispatcher_name(self.client.address),
                selector_index,
            )

        # Fire Home Assistant event for automations
        self.hass.bus.async_fire(
            FLIC_BUTTON_EVENT,
            {
                "device_id": self.device_id,
                "address": self.client.address,
                "event_type": event_type,
                **event_data,
            },
        )

    async def async_update_twist_position(
        self, mode_index: int, percentage: float
    ) -> None:
        """Update a twist slot position and send to the device.

        Args:
            mode_index: Twist mode index (0-11 for slots)
            percentage: Position as percentage (0.0-100.0)

        """
        await self.client.async_send_update_twist_position(mode_index, percentage)

    async def _async_update_data(self) -> dict[str, Any]:
        """Return stored battery data.

        Battery level is fetched via the GET_BATTERY_LEVEL command
        during connection setup. No periodic polling is needed.

        Returns:
            Dictionary with battery voltage

        """
        return self.data or {}
