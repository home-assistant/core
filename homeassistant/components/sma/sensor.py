"""SMA Solar Webconnect interface."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pysma

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, PYSMA_COORDINATOR, PYSMA_DEVICE_INFO, PYSMA_SENSORS


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
        device_info: DeviceInfo,
        pysma_sensor: pysma.sensor.Sensor,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor = pysma_sensor
        self._enabled_default = self._sensor.enabled
        self._config_entry_unique_id = config_entry_unique_id
        self._attr_device_info = device_info

        if self.native_unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_device_class = SensorDeviceClass.ENERGY
        if self.native_unit_of_measurement == POWER_WATT:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_device_class = SensorDeviceClass.POWER

        # Set sensor enabled to False.
        # Will be enabled by async_added_to_hass if actually used.
        self._sensor.enabled = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if self._attr_device_info is None or not (
            name_prefix := self._attr_device_info.get("name")
        ):
            name_prefix = "SMA"

        return f"{name_prefix} {self._sensor.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._sensor.unit

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this sensor."""
        return (
            f"{self._config_entry_unique_id}-{self._sensor.key}_{self._sensor.key_idx}"
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._sensor.enabled = False
