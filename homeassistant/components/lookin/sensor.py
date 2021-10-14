"""The lookin integration sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, LOOKIN_DEVICE, METEO_COORDINATOR
from .models import Device

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    lookin_device = data[LOOKIN_DEVICE]
    meteo_coordinator = data[METEO_COORDINATOR]

    async_add_entities(
        [
            LookinSensor(meteo_coordinator, lookin_device, description)
            for description in SENSOR_TYPES
        ]
    )


class LookinSensor(CoordinatorEntity, Entity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        lookin_device: Device,
        description: SensorEntityDescription,
    ) -> None:
        """Init the lookin sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._lookin_device = lookin_device
        self._attr_name = f"{lookin_device.name} {description.name}"
        self._attr_native_value = getattr(self.coordinator.data, description.key)
        self._attr_unique_id = f"{lookin_device.id}-{description.key}"

    def _handle_coordinator_update(self):
        """Update the state of the entity."""
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._lookin_device.id)},
            "name": self._lookin_device.name,
            "manufacturer": "LOOKin",
            "model": "LOOKin 2",
            "sw_version": self._lookin_device.firmware,
        }
