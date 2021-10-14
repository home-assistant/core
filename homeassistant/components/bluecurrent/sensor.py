"""Support for BlueCurrent sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueCurrentEntity, Connector
from .const import DOMAIN, GRID_SENSORS, SENSORS, TIMESTAMP_KEYS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Blue Current sensors."""
    connector: Connector = hass.data[DOMAIN][entry.entry_id]
    sensor_list: list[BlueCurrentSensor] = []
    for evse_id in connector.charge_points.keys():
        for sensor in SENSORS:
            sensor_list.append(BlueCurrentSensor(connector, sensor, evse_id))

    for grid_sensor in GRID_SENSORS:
        sensor_list.append(BlueCurrentSensor(connector, grid_sensor))

    async_add_entities(sensor_list)


class BlueCurrentSensor(BlueCurrentEntity, SensorEntity):
    """Base charge point sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        connector: Connector,
        sensor: SensorEntityDescription,
        evse_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(connector, evse_id)

        self._key = sensor.key
        self.entity_description = sensor

        self._attr_unique_id = sensor.key
        self.entity_id = f"sensor.{sensor.key}"
        if not self.is_grid:
            self.entity_id += f"_{evse_id}"
            self._attr_unique_id += f"_{evse_id}"

    @callback
    def update_from_latest_data(self) -> None:
        """Update the sensor from the latest data."""

        if self.is_grid:
            new_value = self._connector.grid.get(self._key)
        else:
            new_value = self._connector.charge_points[self._evse_id].get(self._key)

        if new_value is not None:

            if self._key in TIMESTAMP_KEYS and not (
                self._attr_native_value is None or self._attr_native_value < new_value
            ):
                return
            self._attr_available = True
            self._attr_native_value = new_value

        elif self._key not in TIMESTAMP_KEYS:
            self._attr_available = False
