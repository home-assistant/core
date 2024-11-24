"""Support for Adax energy sensors."""

from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .climate import AdaxDataHandler

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Adax energy sensors from a config entry."""
    adax_data_handler = hass.data[entry.entry_id]

    async_add_entities(
        (
            AdaxEnergySensor(adax_data_handler, room)
            for room in adax_data_handler.get_rooms()
        ),
        True,
    )


class AdaxEnergySensor(SensorEntity):
    """Representation of an Adax Energy Sensor."""

    def __init__(self, adax_data_handler: AdaxDataHandler, room: Any) -> None:
        """Initialize the sensor."""
        self._adax_data_handler = adax_data_handler
        self._heater_data = room
        self._last_reset = None
        self._state = None
        self._attr_name = f"Adax Energy Sensor {self._heater_data['name']}"
        self._attr_unique_id = (
            f"adax_energy_{self._heater_data['homeId']}_{self._heater_data['name']}"
        )
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        return self._last_reset

    async def async_update(self) -> None:
        """Get the latest data."""
        _LOGGER.debug(
            "Updating AdaxEnergySensor for room ID %s", self._heater_data["id"]
        )
        room = self._adax_data_handler.get_room(self._heater_data["id"])
        if room:
            if self._state is not None:
                old_state = float(self._state)
            else:
                old_state = 0
            self._heater_data = room
            self._state = room.get("energyWh", 0) / 1000
            _LOGGER.debug("Updated state: %s kWh", self._state)
            if int(self._state * 1000) < int(old_state * 1000):
                self._last_reset = datetime.now(UTC)
        else:
            _LOGGER.warning(
                "Room ID %s not found in data handler", self._heater_data["id"]
            )
