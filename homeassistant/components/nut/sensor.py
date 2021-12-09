"""Provides a sensor to track various status aspects of a UPS."""
from __future__ import annotations

import logging

from homeassistant.components.nut import PyNUTData
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    COORDINATOR,
    DOMAIN,
    KEY_STATUS,
    KEY_STATUS_DISPLAY,
    PYNUT_DATA,
    PYNUT_UNIQUE_ID,
    SENSOR_TYPES,
    STATE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the NUT sensors."""

    pynut_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = pynut_data[COORDINATOR]
    data = pynut_data[PYNUT_DATA]
    unique_id = pynut_data[PYNUT_UNIQUE_ID]
    status = coordinator.data

    resources = [sensor_id for sensor_id in SENSOR_TYPES if sensor_id in status]
    # Display status is a special case that falls back to the status value
    # of the UPS instead.
    if KEY_STATUS in resources:
        resources.append(KEY_STATUS_DISPLAY)

    entities = [
        NUTSensor(
            coordinator,
            SENSOR_TYPES[sensor_type],
            data,
            unique_id,
        )
        for sensor_type in resources
    ]

    async_add_entities(entities, True)


class NUTSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor entity for NUT status values."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_description: SensorEntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description

        device_name = data.name.title()
        self._attr_name = f"{device_name} {sensor_description.name}"
        self._attr_unique_id = f"{unique_id}_{sensor_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_device_info.update(data.device_info)

    @property
    def native_value(self):
        """Return entity state from ups."""
        status = self.coordinator.data
        if self.entity_description.key == KEY_STATUS_DISPLAY:
            return _format_display_state(status)
        return status.get(self.entity_description.key)


def _format_display_state(status):
    """Return UPS display state."""
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN
