"""Number platform for Aeroflex adjustable bed."""

from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    FEET_MOTION_TIME,
    HEAD_MOTION_TIME,
    MAX_FEET_ANGLE,
    MAX_HEAD_ANGLE,
    MIN_ANGLE,
    RX_UUID,
    STEP_DURATION,
    BedCommand,
)
from .entity import AeroflexBedEntity

_LOGGER = logging.getLogger(__name__)


class AeroflexBedNumber(AeroflexBedEntity, NumberEntity):
    """Representation of an Aeroflex Adjustable Bed angle control."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ble_device: BLEDevice,
        name: str,
        key: str,
        command_up: BedCommand,
        command_down: BedCommand,
        initial_value: float = 0,
        max_angle: float = MAX_HEAD_ANGLE,
        motion_time: float = HEAD_MOTION_TIME,
    ) -> None:
        """Initialize the bed angle entity."""
        super().__init__(hass, entry, ble_device)
        self._attr_name = name
        self._key = key
        self._command_up = command_up
        self._command_down = command_down
        self._attr_native_value = initial_value
        self._attr_native_min_value = MIN_ANGLE
        self._attr_native_max_value = max_angle
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = DEGREE
        self._attr_icon = "mdi:bed-king"
        self._attr_unique_id = f"{ble_device.address}_{key}"
        self._motion_time = motion_time  # Time for full range motion
        self._max_angle = max_angle  # Maximum angle for this control

    async def async_set_native_value(self, value: float) -> None:
        """Set the angle value."""
        current_value = self._attr_native_value or 0

        if value == current_value:
            return

        try:
            # Calculate the angle difference
            angle_diff = abs(value - current_value)

            # Calculate what percentage of the full range we need to move
            percentage_of_range = angle_diff / self._max_angle

            # Calculate the duration needed based on the percentage of full motion time
            duration_seconds = self._motion_time * percentage_of_range

            if value > current_value:
                # Need to increase angle
                await self._send_command(self._command_up, duration_seconds)
            else:
                # Need to decrease angle
                await self._send_command(self._command_down, duration_seconds)

            self._attr_native_value = value
            self.async_write_ha_state()
        except BleakError as error:
            _LOGGER.error("Error setting %s to %s: %s", self._key, value, error)

    async def _send_command(self, command: BedCommand, duration_seconds: float) -> None:
        """Send command to the BLE device in a loop for the specified duration."""
        # Use the bed-specific lock to ensure only one command is sent at a time
        async with self._command_lock:
            _LOGGER.debug(
                "Sending command %s for duration %s seconds to device %s",
                command,
                duration_seconds,
                self._ble_device.address,
            )

            try:
                # Connect to the device
                async with BleakClient(self._ble_device) as client:
                    if not client.is_connected:
                        _LOGGER.error(
                            "Failed to connect to device %s", self._ble_device.address
                        )
                        return

                    # Calculate how many commands we need to send
                    num_commands = int(duration_seconds / STEP_DURATION)

                    # Ensure we send at least one command
                    num_commands = max(1, num_commands)

                    _LOGGER.debug(
                        "Sending %s commands with %s second intervals",
                        num_commands,
                        STEP_DURATION,
                    )

                    # Send the command repeatedly
                    start_time = time.time()
                    for _ in range(num_commands):
                        # Format: [command]
                        command_bytes = bytes([int(command)])
                        await client.write_gatt_char(RX_UUID, command_bytes)

                        # Sleep for the step duration
                        await asyncio.sleep(STEP_DURATION)

                    elapsed = time.time() - start_time
                    _LOGGER.debug(
                        "Command sequence completed in %s seconds (expected %s)",
                        elapsed,
                        duration_seconds,
                    )

            except BleakError as error:
                _LOGGER.error(
                    "Error sending command to device %s: %s",
                    self._ble_device.address,
                    error,
                )
                raise


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aeroflex bed number entities from config entry."""
    # Get the BLE device from the entry
    ble_device = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AeroflexBedNumber(
            hass,
            entry,
            ble_device,
            "Head Angle",
            "head_angle",
            BedCommand.HEAD_UP,
            BedCommand.HEAD_DOWN,
            initial_value=0,
            max_angle=MAX_HEAD_ANGLE,
            motion_time=HEAD_MOTION_TIME,
        ),
        AeroflexBedNumber(
            hass,
            entry,
            ble_device,
            "Feet Angle",
            "feet_angle",
            BedCommand.FEET_UP,
            BedCommand.FEET_DOWN,
            initial_value=0,
            max_angle=MAX_FEET_ANGLE,
            motion_time=FEET_MOTION_TIME,
        ),
    ]

    async_add_entities(entities)
