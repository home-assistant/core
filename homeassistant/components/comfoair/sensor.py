"""Platform to control a Zehnder ComfoAir 350 ventilation unit."""

import logging

from comfoair.asyncio import ComfoAir

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, ComfoAirModule

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
    ],
    ATTR_OUTSIDE_TEMPERATURE: [
        "Outside Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_OUTSIDE,
    ],
    ATTR_SUPPLY_TEMPERATURE: [
        "Supply Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_SUPPLY,
    ],
    ATTR_RETURN_TEMPERATURE: [
        "Return Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_RETURN,
    ],
    ATTR_EXHAUST_TEMPERATURE: [
        "Exhaust Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        ComfoAir.TEMP_EXHAUST,
    ],
    ATTR_AIR_FLOW_EXHAUST: [
        "Exhaust airflow",
        "%",
        "mdi:fan",
        ComfoAir.AIRFLOW_EXHAUST,
    ],
    ATTR_AIR_FLOW_SUPPLY: ["Supply airflow", "%", "mdi:fan", ComfoAir.AIRFLOW_SUPPLY],
    ATTR_FAN_SPEED_MODE: ["Speed mode", "", "mdi:fan", ComfoAir.FAN_SPEED_MODE],
}


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the ComfoAir sensor platform."""
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


class ComfoAirSensor(Entity):
    """Representation of a ComfoAir sensor."""

    def __init__(self, name, ca: ComfoAirModule, sensor_type) -> None:
        """Initialize the ComfoAir sensor."""
        self._ca = ca
        self._sensor_type = sensor_type
        self._unit = SENSOR_TYPES[self._sensor_type][1]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._attr = SENSOR_TYPES[self._sensor_type][3]
        self._name = name
        self._data = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        async def async_handle_update(attr, value):
            _LOGGER.debug("Dispatcher update for %s: %s", attr, value)
            assert attr == self._attr
            self._data = value
            self.async_schedule_update_ha_state()

        self._ca.add_cooked_listener(self._attr, async_handle_update)

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit
