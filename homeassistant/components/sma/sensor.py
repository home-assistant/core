"""SMA Solar Webconnect interface."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pysma

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, PYSMA_COORDINATOR, PYSMA_DEVICE_INFO, PYSMA_SENSORS
from .entities import SENSOR_ENTITIES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMA sensors."""
    sma_data = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = sma_data[PYSMA_COORDINATOR]
    used_sensors = sma_data[PYSMA_SENSORS]
    device_info = sma_data[PYSMA_DEVICE_INFO]

    if TYPE_CHECKING:
        assert config_entry.unique_id

    entities = []
    for sensor in used_sensors:
        entities.append(
            SMAsensor(
                coordinator,
                config_entry.unique_id,
                SENSOR_ENTITIES.get(sensor.name),
                device_info,
                sensor,
            )
        )

    async_add_entities(entities)


class SMAsensor(CoordinatorEntity, SensorEntity):
    """Representation of a SMA sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry_unique_id: str,
        description: SensorEntityDescription | None,
        device_info: DeviceInfo,
        pysma_sensor: pysma.sensor.Sensor,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        if description is not None:
            self.entity_description = description
        else:
            self._attr_name = pysma_sensor.name

        self._sensor = pysma_sensor

        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{config_entry_unique_id}-{self._sensor.key}_{self._sensor.key_idx}"
        )

        # Set sensor enabled to False.
        # Will be enabled by async_added_to_hass if actually used.
        self._sensor.enabled = False

    @property
    def name(self) -> str:
        """Return the name of the sensor prefixed with the device name."""
        if self._attr_device_info is None or not (
            name_prefix := self._attr_device_info.get("name")
        ):
            name_prefix = "SMA"

        return f"{name_prefix} {super().name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._sensor.enabled = False
