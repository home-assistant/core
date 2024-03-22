"""The Things Network's integration sensors."""
import logging

from ttn_client import TTNSensorValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTRY_DATA_COORDINATOR
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add entities for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id][ENTRY_DATA_COORDINATOR]

    sensors: dict[str, TtnDataSensor] = {}

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_sensors = {
            unique_id: TtnDataSensor(
                coordinator,
                ttn_value,
            )
            for device_id, device_uplinks in data.items()
            for field_id, ttn_value in device_uplinks.items()
            for unique_id in set(TtnDataSensor.get_unique_id(device_id, field_id))
            if unique_id not in sensors and isinstance(ttn_value, TTNSensorValue)
        }
        async_add_entities(new_sensors.values())
        sensors.update(new_sensors)

    coordinator.async_add_listener(_async_measurement_listener)


class TtnDataSensor(TTNEntity, SensorEntity):
    """Represents a TTN Home Assistant Sensor."""

    @property
    def native_value(self) -> float | int | str:
        """Return the state of the entity."""
        value: float | int | str = self._ttn_value.value
        return value
