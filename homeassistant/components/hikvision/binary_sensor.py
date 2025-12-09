"""Support for Hikvision event stream events represented as binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import DEVICE_CLASS_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision binary sensors from a config entry."""
    data = entry.runtime_data
    camera = data.camera

    sensors = camera.current_event_states
    if sensors is None or not sensors:
        _LOGGER.warning("Hikvision device has no sensors available")
        return

    entities: list[HikvisionBinarySensor] = []

    for sensor_type, channel_list in sensors.items():
        for channel_info in channel_list:
            channel = channel_info[1]
            entities.append(
                HikvisionBinarySensor(
                    entry=entry,
                    sensor_type=sensor_type,
                    channel=channel,
                )
            )

    async_add_entities(entities)


class HikvisionBinarySensor(BinarySensorEntity):
    """Representation of a Hikvision binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        sensor_type: str,
        channel: int,
    ) -> None:
        """Initialize the binary sensor."""
        self._entry = entry
        self._data = entry.runtime_data
        self._camera = self._data.camera
        self._sensor_type = sensor_type
        self._channel = channel

        # Build unique ID
        self._attr_unique_id = f"{self._data.device_id}_{sensor_type}_{channel}"

        # Build entity name based on device type
        if self._data.device_type == "NVR":
            self._attr_name = f"{sensor_type} {channel}"
        else:
            self._attr_name = sensor_type

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._data.device_id)},
            name=self._data.device_name,
            manufacturer="Hikvision",
            model=self._data.device_type,
        )

        # Set device class
        self._attr_device_class = DEVICE_CLASS_MAP.get(sensor_type)

        # Callback ID for pyhik
        self._callback_id = f"{self._data.device_id}.{sensor_type}.{channel}"
        self._cancel_timer: CALLBACK_TYPE | None = None

    def _get_sensor_attributes(self) -> tuple[bool, Any, Any, Any]:
        """Get sensor attributes from camera."""
        return self._camera.fetch_attributes(self._sensor_type, self._channel)

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._get_sensor_attributes()[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = self._get_sensor_attributes()
        return {ATTR_LAST_TRIP_TIME: attrs[3]}

    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added."""
        await super().async_added_to_hass()

        # Register callback with pyhik
        self._camera.add_update_callback(self._update_callback, self._callback_id)

        # Register cleanup
        self.async_on_remove(self._remove_callback)

    @callback
    def _remove_callback(self) -> None:
        """Remove the callback from pyhik."""
        # Cancel any pending timer
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _update_callback(self, msg: str) -> None:
        """Update the sensor's state when callback is triggered."""
        self.async_write_ha_state()
