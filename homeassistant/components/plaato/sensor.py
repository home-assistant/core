"""Support for Plaato Airlock sensors."""

from __future__ import annotations

from pyplaato.models.device import PlaatoDevice
from pyplaato.plaato import PlaatoKeg

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ATTR_TEMP, SENSOR_UPDATE
from .const import CONF_USE_WEBHOOK, SENSOR_SIGNAL
from .coordinator import PlaatoConfigEntry, PlaatoCoordinator, PlaatoData
from .entity import PlaatoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Plaato sensor."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlaatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plaato from a config entry."""
    entry_data = entry.runtime_data

    @callback
    def _async_update_from_webhook(device_id, sensor_data: PlaatoDevice):
        """Update/Create the sensors."""
        entry_data.sensor_data = sensor_data

        if device_id != entry_data.device_id:
            entry_data.device_id = device_id
            async_add_entities(
                [
                    PlaatoSensor(entry_data, sensor_type)
                    for sensor_type in sensor_data.sensors
                ]
            )
        else:
            for sensor_type in sensor_data.sensors:
                async_dispatcher_send(hass, SENSOR_SIGNAL % (device_id, sensor_type))

    if entry.data[CONF_USE_WEBHOOK]:
        async_dispatcher_connect(hass, SENSOR_UPDATE, _async_update_from_webhook)
    else:
        coordinator = entry_data.coordinator
        assert coordinator is not None
        async_add_entities(
            PlaatoSensor(entry_data, sensor_type, coordinator)
            for sensor_type in coordinator.data.sensors
        )


class PlaatoSensor(PlaatoEntity, SensorEntity):
    """Representation of a Plaato Sensor."""

    def __init__(
        self,
        data: PlaatoData,
        sensor_type: str,
        coordinator: PlaatoCoordinator | None = None,
    ) -> None:
        """Initialize plaato sensor."""
        super().__init__(data, sensor_type, coordinator)
        if sensor_type is PlaatoKeg.Pins.TEMPERATURE or sensor_type == ATTR_TEMP:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self._sensor_data.sensors.get(self._sensor_type)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._sensor_data.get_unit_of_measurement(self._sensor_type)
