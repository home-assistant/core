"""Support for Nee-Vo Tank Monitors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NeeVoEntity
from .const import DOMAIN, TANKS

_LOGGER = logging.getLogger(__name__)

TANK_LEVEL = "tank_level"
TANK_LAST_PRESSURE = "tank_last_pressure"

SENSOR_NAMES_TO_ATTRIBUTES = {
    TANK_LEVEL: "level",
    TANK_LAST_PRESSURE: "TankLastPressure",
}

SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT = {
    TANK_LEVEL: PERCENTAGE,
    TANK_LAST_PRESSURE: UnitOfPressure.KPA,  # default is kPa
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Nee-Vo sensor based on a config entry."""

    tanks = hass.data[DOMAIN][TANKS][entry.entry_id]
    sensors = []
    all_tanks = tanks.copy()

    for _equip in all_tanks.values():
        _LOGGER.debug("Adding sensors for %s", _equip)
        for name, attribute in SENSOR_NAMES_TO_ATTRIBUTES.items():
            if getattr(_equip, attribute, None) is not None:
                sensors.append(NeeVoSensor(_equip, name))

    async_add_entities(sensors)


class NeeVoSensor(NeeVoEntity, SensorEntity):
    """Define a Nee-Vo sensor."""

    def __init__(self, neevo_tank, device_name):
        """Initialize."""
        super().__init__(neevo_tank)
        self._neevo = neevo_tank
        self._device_name = device_name
        self._attr_device_class = None
        self._attr_state_class = "measurement"

    @property
    def native_value(self) -> float:
        """Return sensors state."""
        value = getattr(self._neevo, SENSOR_NAMES_TO_ATTRIBUTES[self._device_name])
        if isinstance(value, float):
            value = round(value, 2)
        return value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        unit_of_measurement = SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT[self._device_name]
        if self._device_name == TANK_LAST_PRESSURE:
            if self._neevo.last_pressure_unit is not None:
                unit_of_measurement = UnitOfPressure(self._neevo.last_pressure_unit)
        return unit_of_measurement

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._neevo.name}_{self._device_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return f"{self._neevo.id}_{self._neevo.name}_{self._device_name}"
