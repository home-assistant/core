"""Coordinator for Flic Button integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakError
from pyflic_ble import DeviceCapabilities, FlicClient, FlicProtocolError
from pyflic_ble.handlers.base import DeviceProtocolHandler

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_device_registry_updated_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEVICE_TYPE_MODEL_NAMES, DOMAIN, FLIC_BUTTON_EVENT, DeviceType

_LOGGER = logging.getLogger(__name__)

SIGNAL_BUTTON_EVENT = f"{DOMAIN}_button_event_{{0}}"
SIGNAL_ROTATE_EVENT = f"{DOMAIN}_rotate_event_{{0}}"


def _address_key(address: str) -> str:
    """Return colon-stripped lowercase MAC for use in signal names."""
    return address.replace(":", "").lower()


def format_event_dispatcher_name(address: str) -> str:
    """Format dispatcher signal name for button events."""
    return SIGNAL_BUTTON_EVENT.format(_address_key(address))


def format_rotate_dispatcher_name(address: str) -> str:
    """Format dispatcher signal name for rotate events."""
    return SIGNAL_ROTATE_EVENT.format(_address_key(address))


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
        """Initialize the coordinator."""
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

        # Set up client callbacks
        self.client.on_button_event = self._handle_button_event
        self.client.on_rotate_event = self._handle_rotate_event
        self.client.on_disconnect = self._handle_disconnect

        # Set initial data with battery level from pairing
        if battery_level is not None:
            self.data = {
                "battery_voltage": FlicClient.battery_raw_to_voltage(
                    battery_level, self.device_type
                )
            }
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
        """Return the device type."""
        return self.client.device_type

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
                voltage = await self.client.get_battery_voltage()
                self.data = {"battery_voltage": voltage}
                _LOGGER.debug(
                    "Battery voltage for %s: %.3fV",
                    self.client.address,
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
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to retrieve firmware version from %s",
                    self.client.address,
                )

            # Read device name (non-fatal on failure)
            device_name: str | None = None
            try:
                device_name, _ = await self.client.get_name()
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to retrieve device name from %s",
                    self.client.address,
                )

            # Update device registry with firmware version and name
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.client.address)}
            )
            if device:
                if self._firmware_version is not None:
                    device_registry.async_update_device(
                        device.id,
                        sw_version=str(self._firmware_version),
                    )
                if device_name and device.name_by_user is None:
                    device_registry.async_update_device(
                        device.id,
                        name_by_user=device_name,
                    )
                    _LOGGER.debug(
                        "Synced device name from %s: %s",
                        self.client.address,
                        device_name,
                    )

            self._connected = True
            _LOGGER.info("Successfully connected to %s", self.client.address)

        except (TimeoutError, BleakError, FlicProtocolError) as err:
            self._connected = False
            _LOGGER.error("Failed to connect to %s: %s", self.client.address, err)
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from button."""
        self._connected = False
        await self.client.disconnect()

    async def async_reconnect_if_needed(self) -> None:
        """Reconnect to button if disconnected."""

        async with self._reconnect_lock:
            _LOGGER.debug("Client is connected: %s", self.client.is_connected)
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
    def _handle_disconnect(self) -> None:
        """Handle BLE disconnection detected by the client."""
        if self._connected:
            _LOGGER.info("Connection lost to %s", self.client.address)
            self._connected = False
            self.async_set_updated_data(self.data)

        self.hass.async_create_background_task(
            self.async_reconnect_if_needed(),
            name=f"{DOMAIN}_reconnect_{self.client.address}",
        )

    @callback
    def _handle_button_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle button event from client."""
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

        The library pre-processes rotation events: in DEFAULT/CONTINUOUS mode
        it emits quantized increment/decrement events, in SELECTOR mode it
        emits raw rotate_clockwise/rotate_counter_clockwise events.
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
    def async_register_device_name_listener(self) -> CALLBACK_TYPE | None:
        """Register a listener to push HA device renames to the physical device."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.client.address)}
        )
        if not device:
            return None

        @callback
        def _async_on_device_registry_update(
            event: Event[dr.EventDeviceRegistryUpdatedData],
        ) -> None:
            """Handle device registry updates."""
            if event.data["action"] != "update":
                return
            if "name_by_user" not in event.data["changes"]:
                return

            device_entry = device_registry.async_get(event.data["device_id"])
            if not device_entry or not device_entry.name_by_user:
                return

            self.hass.async_create_background_task(
                self._async_push_name_to_device(device_entry.name_by_user),
                name=f"{DOMAIN}_push_name_{self.client.address}",
            )

        return async_track_device_registry_updated_event(
            self.hass,
            device.id,
            _async_on_device_registry_update,
        )

    async def _async_push_name_to_device(self, name: str) -> None:
        """Push a name change to the physical device."""
        if not self._connected or not self.client.is_connected:
            _LOGGER.debug(
                "Cannot push name to %s: device not connected",
                self.client.address,
            )
            return

        try:
            confirmed_name, _ = await self.client.set_name(name)
            _LOGGER.debug(
                "Pushed name to %s: %s (confirmed: %s)",
                self.client.address,
                name,
                confirmed_name,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to push name to %s",
                self.client.address,
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Return stored battery data (no polling needed)."""
        return self.data or {}
