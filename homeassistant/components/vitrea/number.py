"""Number platform for Vitrea integration."""

from __future__ import annotations

import logging
from typing import Any

from vitreaclient.client import VitreaClient
from vitreaclient.constants import DeviceStatus, VitreaResponse

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities from a config entry."""
    if len(entry.runtime_data.timers) > 0:
        _LOGGER.debug("Adding %d new timers entities", len(entry.runtime_data.timers))
        async_add_entities(entry.runtime_data.timers)
        entry.runtime_data.client.on(
            VitreaResponse.STATUS, lambda data: _handle_timer_event(entry, data)
        )


def _handle_timer_event(entry: ConfigEntry, event: Any) -> None:
    """Handle timer events from Vitrea client."""
    _LOGGER.debug("Handling timer event: %s", event)

    if event.status not in (DeviceStatus.BOILER_ON, DeviceStatus.BOILER_OFF):
        return

    entity_id = f"{event.node}_{event.key}"
    entity: VitreaTimerControl | None = None

    for timer in entry.runtime_data.timers:
        if timer.unique_id == entity_id:
            entity = timer
            break

    if entity is None:
        _LOGGER.warning("Timer entity not found: %s", entity_id)
    else:
        # Update the timer value based on the event data
        _LOGGER.debug("Updating timer entity %s with value %s", entity_id, event.data)
        entity.set_timer_value(int(event.data))
        entity.async_write_ha_state()


class VitreaTimerControl(NumberEntity):
    """Representation of a Vitrea timer control."""

    _attr_native_min_value = 0
    _attr_native_max_value = 120  # 2 hours in minutes
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = NumberDeviceClass.DURATION

    def __init__(
        self,
        node: str,
        key: str,
        initial_value: str,
        monitor: VitreaClient,
    ) -> None:
        """Initialize the timer control."""
        self.monitor = monitor
        self._node = node
        self._key = key
        self._name = f"timer_{node}_{key}"
        self._attr_unique_id = f"{node}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{node}_{key}")},
            "name": "Boiler Timer",
            "manufacturer": "Vitrea",
            "model": "Timer Control",
        }

        # Initialize with the current timer value from the device
        try:
            self._attr_native_value = float(initial_value)
        except (ValueError, TypeError):
            self._attr_native_value = 0.0

        # Store the last set value as default
        self._default_value: float = self._attr_native_value

        # Debug information to help verify entity is created
        _LOGGER.debug(
            "Created timer control entity: %s with value %s",
            self._attr_unique_id,
            self._attr_native_value,
        )

    @property
    def name(self) -> str:
        """Return the name of the timer control."""
        return self._name

    @property
    def default_value(self) -> float:
        """Return the default timer value."""
        return self._default_value

    @default_value.setter
    def default_value(self, value: float) -> None:
        """Set the default timer value."""
        self._default_value = value

    async def async_set_native_value(self, value: float) -> None:
        """Set the timer value for the associated switch."""
        minutes = int(value)
        _LOGGER.debug(
            "Setting timer value to %d minutes for switch %s/%s",
            minutes,
            self._node,
            self._key,
        )
        try:
            # Call the monitor's set_timer method to update the timer
            await self.monitor.set_timer(self._node, self._key, minutes)

            # Update the entity's value
            self._attr_native_value = value

            # Store this as the new default value if it's not 0
            if self._attr_native_value > 0:
                self._default_value = self._attr_native_value
            self.async_write_ha_state()
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to set timer value: %s", err)

    def set_timer_value(self, value: int) -> None:
        """Set the timer value internally."""
        self._attr_native_value = float(value)
