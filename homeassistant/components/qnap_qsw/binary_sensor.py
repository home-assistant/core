"""Support for the QNAP QSW service."""
from __future__ import annotations

from qnap_qsw.const import (
    DATA_CONDITION_ANOMALY,
    DATA_CONDITION_MESSAGE,
    DATA_CONFIG_URL,
    DATA_FIRMWARE,
    DATA_PRODUCT,
    DATA_SERIAL,
    DATA_UPDATE,
    DATA_UPDATE_VERSION,
)

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QnapQswDataUpdateCoordinator
from .const import BINARY_SENSOR_TYPES, DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW entities from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    binary_sensors = []

    device_info: DeviceInfo = {
        "configuration_url": coordinator.data[DATA_CONFIG_URL],
        "identifiers": {(DOMAIN, coordinator.data[DATA_SERIAL])},
        "manufacturer": MANUFACTURER,
        "model": coordinator.data[DATA_PRODUCT],
        "name": coordinator.data[DATA_PRODUCT],
        "sw_version": coordinator.data[DATA_FIRMWARE],
    }

    for description in BINARY_SENSOR_TYPES:
        if description.key in coordinator.data:
            binary_sensors.append(
                QnapQswBinarySensor(coordinator, description, device_info)
            )

    async_add_entities(binary_sensors, False)


class QnapQswBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Define a QNAP QSW sensor."""

    def __init__(
        self,
        coordinator: QnapQswDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_name = f"{coordinator.data[DATA_PRODUCT]} {description.name}"
        self._attr_unique_id = (
            f"{coordinator.data[DATA_SERIAL].lower()}_{description.key}"
        )
        self.entity_description = description

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        _state_attr = None
        if self.entity_description.key == DATA_CONDITION_ANOMALY:
            _state_attr = {
                "message": self.coordinator.data[DATA_CONDITION_MESSAGE],
            }
        elif self.entity_description.key == DATA_UPDATE:
            _state_attr = {
                "current_version": self.coordinator.data[DATA_FIRMWARE],
                "latest_version": self.coordinator.data[DATA_UPDATE_VERSION],
            }
        return _state_attr

    @property
    def is_on(self):
        """Return the state."""
        return self.coordinator.data[self.entity_description.key]
