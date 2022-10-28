"""Sensor for retrieving Maico Centralized ventilation device information."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# # from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

# # from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity, entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# # from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
# from homeassistant.util import Throttle
from .const import DOMAIN
from .coordinator import MaicoUpdater

LOGGER = logging.getLogger(__name__)

# ICON_HAPPY = "mdi:fan-chevron-down"
# ICON_OTHER = "mdi:fan"
# ICON_SAD = "mdi:fan-alert"


# class MaicoData:
#     """Maico Data object."""

#     def __init__(self, interval, maico_url):
#         """Init Maico Data object."""
#         self.maico_details = None
#         self.update = Throttle(interval)(self._update)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: MaicoUpdater = hass.data[DOMAIN][config_entry.entry_id]
    created = set()
    all_sensors = coordinator.data["sensors"]

    @callback
    def _create_entity(key: str) -> MaicoSensor:
        """Create a sensor entity."""
        created.add(key)
        # data = coordinator.data["sensors"][key]
        # description = ENTITY_DESCRIPTION_KEY_MAP.get(
        #     data.getUnit(), IotaWattSensorEntityDescription("base_sensor")
        # )
        description = MaicoSensorEntityDescription(
            "capteur maico", state_class=SensorStateClass.MEASUREMENT
        )

        return MaicoSensor(
            coordinator=coordinator,
            key=key,
            entity_description=description,
        )

    async_add_entities(_create_entity(key) for key in all_sensors)

    @callback
    def new_data_received():
        """Check for new sensors."""
        entities = [_create_entity(key) for key in all_sensors if key not in created]
        async_add_entities(entities)

    coordinator.async_add_listener(new_data_received)


@dataclass
class MaicoSensorEntityDescription(SensorEntityDescription):
    """Class describing Maico sensor entities."""

    value: Callable | None = None


class MaicoSensor(CoordinatorEntity[MaicoUpdater], SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    entity_description: MaicoSensorEntityDescription

    def __init__(
        self,
        coordinator: MaicoUpdater,
        key: str,
        entity_description: MaicoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self._key = key
        # data = self._sensor_data
        # if data.getType() == "Input":
        #     self._attr_unique_id = (
        #         f"{data.hub_mac_address}-input-{data.getChannel()}-{data.getUnit()}"
        #     )
        self.entity_description = entity_description

    @property
    def _sensor_data(self):
        """Return sensor data."""
        if self._key in self.coordinator.data["sensors"]:
            return self.coordinator.data["sensors"][self._key]

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        if self._key in self.coordinator.data["sensors"]:
            return self._key
        return None

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return device info."""
        return entity.DeviceInfo(
            manufacturer="Maico",
            model="WS320KB",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._key not in self.coordinator.data["sensors"]:
            if self._attr_unique_id:
                entity_registry.async_get(self.hass).async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove())
            return

        super()._handle_coordinator_update()

    # @property
    # def extra_state_attributes(self) -> dict[str, str]:
    #     """Return the extra state attributes of the entity."""
    #     data = self._sensor_data
    #     attrs = {"type": data.getType()}
    #     if attrs["type"] == "Input":
    #         attrs["channel"] = data.getChannel()

    #     return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if func := self.entity_description.value:
            return func(self._sensor_data)
        return self._sensor_data
