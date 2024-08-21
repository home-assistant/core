"""The Things Network's integration binary sensors."""

import logging

from ttn_client import TTNBinarySensorValue

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_APP_ID, DOMAIN
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add binary sensors for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    binary_sensors: set[tuple[str, str]] = set()

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_binary_sensors = {
            (device_id, field_id): TtnBinarySensor(
                coordinator,
                entry.data[CONF_APP_ID],
                ttn_value,
            )
            for device_id, device_uplinks in data.items()
            for field_id, ttn_value in device_uplinks.items()
            if (device_id, field_id) not in binary_sensors
            and isinstance(ttn_value, TTNBinarySensorValue)
        }
        if len(new_binary_sensors):
            async_add_entities(new_binary_sensors.values())
        binary_sensors.update(new_binary_sensors.keys())

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


class TtnBinarySensor(TTNEntity, BinarySensorEntity):
    """Represents a TTN Home Assistant Sensor."""

    _ttn_value: TTNBinarySensorValue

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self._ttn_value.value)
