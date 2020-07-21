"""Platform to control a Zehnder ComfoAir 350 ventilation unit."""

import logging
from typing import Any, Dict, Optional

from comfoair.asyncio import ComfoAir

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import ComfoAirModule
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_COMFORT_TEMPERATURE = "comfort_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_SUPPLY_TEMPERATURE = "supply_temperature"
ATTR_RETURN_TEMPERATURE = "return_temperature"
ATTR_EXHAUST_TEMPERATURE = "exhaust_temperature"
ATTR_AIR_FLOW_SUPPLY = "air_flow_supply"
ATTR_AIR_FLOW_EXHAUST = "air_flow_exhaust"
ATTR_FAN_SPEED_MODE = "speed_mode"

SENSOR_TYPES = {
    ATTR_COMFORT_TEMPERATURE: [
        "Comfort Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_COMFORT,
        DEVICE_CLASS_TEMPERATURE,
    ],
    ATTR_OUTSIDE_TEMPERATURE: [
        "Outside Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_OUTSIDE,
        DEVICE_CLASS_TEMPERATURE,
    ],
    ATTR_SUPPLY_TEMPERATURE: [
        "Supply Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_SUPPLY,
        DEVICE_CLASS_TEMPERATURE,
    ],
    ATTR_RETURN_TEMPERATURE: [
        "Return Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_RETURN,
        DEVICE_CLASS_TEMPERATURE,
    ],
    ATTR_EXHAUST_TEMPERATURE: [
        "Exhaust Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_EXHAUST,
        DEVICE_CLASS_TEMPERATURE,
    ],
    ATTR_AIR_FLOW_EXHAUST: [
        "Exhaust airflow",
        "%",
        "mdi:fan",
        ComfoAir.AIRFLOW_EXHAUST,
        None,
    ],
    ATTR_AIR_FLOW_SUPPLY: [
        "Supply airflow",
        "%",
        "mdi:fan",
        ComfoAir.AIRFLOW_SUPPLY,
        None,
    ],
    ATTR_FAN_SPEED_MODE: ["Speed mode", "", "mdi:fan", ComfoAir.FAN_SPEED_MODE, None],
}


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up the ComfoAir sensor config entry."""
    unit = hass.data[DOMAIN]

    sensors = []
    for resource in SENSOR_TYPES:
        sensors.append(
            ComfoAirSensor(
                name=f"{unit.name} {SENSOR_TYPES[resource][0]}",
                ca=unit,
                sensor_type=resource,
            )
        )

    async_add_entities(sensors, True)
    return True


class ComfoAirSensor(Entity):
    """Representation of a ComfoAir sensor."""

    def __init__(self, name, ca: ComfoAirModule, sensor_type) -> None:
        """Initialize the ComfoAir sensor."""
        self._ca = ca
        self._sensor_type = sensor_type
        self._unit = SENSOR_TYPES[self._sensor_type][1]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._attr = SENSOR_TYPES[self._sensor_type][3]
        self._class = SENSOR_TYPES[self._sensor_type][4]
        self._name = name
        self._unique_id = name
        self._data = None
        self._handler = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        async def _async_handle_update(attr, value):
            _LOGGER.debug("Dispatcher update for %s: %s", attr, value)
            assert attr == self._attr
            self._data = value
            self.async_schedule_update_ha_state()

        self._handler = _async_handle_update
        self._ca.add_cooked_listener(self._attr, self._handler)

    async def async_will_remove_from_hass(self):
        """Unregister sensor updates."""
        self._ca.remove_cooked_listener(self._attr, self._handler)

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def state(self) -> Optional[str]:
        """Return the state of the entity."""
        return self._data

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device specific attributes."""
        return self._ca.device_info

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._class

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return self._unique_id
