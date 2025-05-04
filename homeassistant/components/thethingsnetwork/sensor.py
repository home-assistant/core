"""The Things Network's integration sensors."""

import logging

from ttn_client import TTNSensorValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_APP_ID, DOMAIN
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: set[tuple[str, str]] = set()

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_sensors = {
            (device_id, field_id): TtnDataSensor(
                coordinator,
                entry.data[CONF_APP_ID],
                ttn_value,
            )
            for device_id, device_uplinks in data.items()
            for field_id, ttn_value in device_uplinks.items()
            if (device_id, field_id) not in sensors
            and isinstance(ttn_value, TTNSensorValue)
        }
        if new_sensors:
            async_add_entities(new_sensors.values())
        sensors.update(new_sensors.keys())

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


class TtnDataSensor(TTNEntity, SensorEntity):
    """Represents a TTN Home Assistant Sensor."""

    _ttn_value: TTNSensorValue

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self._ttn_value.value
