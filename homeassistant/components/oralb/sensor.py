"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=1)


@dataclass
class OralBSensorEntityDescription(SensorEntityDescription):
    """Provide a description of a OralB sensor."""

    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None


SENSORS = (
    OralBSensorEntityDescription(
        key="battery",
        name="Battery",
        unique_id="oralb_battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OralBSensorEntityDescription(
        key="status",
        name="Status",
        unique_id="oralb_status",
        icon="mdi:toothbrush-electric",
    ),
    OralBSensorEntityDescription(
        key="brush_time",
        name="Brush Time",
        unique_id="oralb_brushtime",
        native_unit_of_measurement=TIME_SECONDS,
        icon="",
    ),
    OralBSensorEntityDescription(
        key="mode",
        name="Mode",
        unique_id="oralb_mode",
        icon="mdi:tooth",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OralBSensor(data.coordinator, data.device, description)
        for description in SENSORS
    )


class OralBSensor(CoordinatorEntity, SensorEntity):
    """Implementation of the OralB sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, description):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device = device

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.device.ble_device.address)},
            manufacturer="OralB",
            name="OralB Toothbrush",
        )

        self._attr_unique_id = (
            f"{self.device.ble_device.address}_{description.unique_id}"
        )

    @property
    def native_value(self) -> float | None:
        """Return sensor state."""
        value = self.device.result[self.entity_description.key]
        return value
