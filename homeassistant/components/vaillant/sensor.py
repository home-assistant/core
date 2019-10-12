"""Interfaces with Vaillant sensors."""
import logging
from abc import ABC

from pymultimatic.model import BoilerStatus, Room, Component

from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE, DOMAIN, \
    DEVICE_CLASS_PRESSURE

from . import HUB, BaseVaillantEntity, CONF_SENSOR_ROOM_TEMPERATURE, \
    CONF_SENSOR_ZONE_TEMPERATURE, CONF_SENSOR_OUTDOOR_TEMPERATURE, \
    CONF_SENSOR_HOT_WATER_TEMPERATURE, CONF_SENSOR_BOILER_WATER_TEMPERATURE, \
    CONF_SENSOR_BOILER_WATER_PRESSURE

PRESSURE_BAR = 'bar'

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Vaillant sensor platform."""
    sensors = []
    hub = hass.data[HUB]

    if hub.system:
        if hub.system.outdoor_temperature \
                and hub.config[CONF_SENSOR_OUTDOOR_TEMPERATURE]:
            sensors.append(VaillantOutdoorTemperatureSensor(
                hub.system.outdoor_temperature))

        if hub.system.boiler_status:
            if hub.config[CONF_SENSOR_BOILER_WATER_TEMPERATURE]:
                sensors.append(VaillantBoilerTemperatureSensor(
                    hub.system.boiler_status))
            if hub.config[CONF_SENSOR_BOILER_WATER_PRESSURE]:
                sensors.append(VaillantBoilerWaterPressureSensor(
                    hub.system.boiler_status))

        if hub.config[CONF_SENSOR_ZONE_TEMPERATURE]:
            for zone in hub.system.zones:
                if not zone.rbr:
                    sensors.append(VaillantTemperatureSensor(zone))

        if hub.config[CONF_SENSOR_ROOM_TEMPERATURE]:
            for room in hub.system.rooms:
                sensors.append(VaillantTemperatureSensor(room))

        if hub.system.hot_water \
                and hub.config[CONF_SENSOR_HOT_WATER_TEMPERATURE]:
            sensors.append(VaillantTemperatureSensor(hub.system.hot_water))

    _LOGGER.info("Adding %s sensor entities", len(sensors))

    async_add_entities(sensors)
    return True


class BaseVaillantTemperatureSensor(BaseVaillantEntity, ABC):
    """Base temperature sensor class."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TEMP_CELSIUS


class VaillantTemperatureSensor(BaseVaillantTemperatureSensor):
    """Temperature sensor of a vaillant component (HotWater, Zone or Room)."""

    def __init__(self, component):
        """Initialize entity."""
        if isinstance(component, Room):
            super().__init__(DOMAIN, DEVICE_CLASS_TEMPERATURE, component.name,
                             component.name)
        else:
            super().__init__(DOMAIN, DEVICE_CLASS_TEMPERATURE, component.id,
                             component.name)
        self._component: Component = component

    @property
    def state(self):
        """Return the state of the entity."""
        return self._component.current_temperature

    @property
    def available(self):
        """Return True if entity is available."""
        return self._component is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        new_component = self.hub.find_component(self._component)
        if new_component:
            _LOGGER.debug("New / old temperature: %s / %s",
                          new_component.current_temperature,
                          self._component.current_temperature)
        else:
            _LOGGER.debug("Component with id %s doesn't exist anymore",
                          self._component.id)

        self._component = new_component


class VaillantOutdoorTemperatureSensor(BaseVaillantTemperatureSensor):
    """Outdoor temperature sensor."""

    def __init__(self, outdoor_temp):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_TEMPERATURE, 'outdoor',
                         'Outdoor')
        self._outdoor_temp = outdoor_temp

    @property
    def state(self):
        """Return the state of the entity."""
        return self._outdoor_temp

    @property
    def available(self):
        """Return True if entity is available."""
        return self._outdoor_temp is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        _LOGGER.debug("New / old temperature: %s / %s",
                      self.hub.system.outdoor_temperature, self._outdoor_temp)
        self._outdoor_temp = self.hub.system.outdoor_temperature


class VaillantBoilerWaterPressureSensor(BaseVaillantEntity):
    """Water pressure inside the boiler."""

    def __init__(self, boiler_status: BoilerStatus):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_PRESSURE,
                         boiler_status.device_name, boiler_status.device_name)
        self._boiler_status = boiler_status

    @property
    def state(self):
        """Return the state of the entity."""
        return self._boiler_status.water_pressure

    @property
    def available(self):
        """Return True if entity is available."""
        return self._boiler_status is not None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PRESSURE_BAR

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._boiler_status = self.hub.system.boiler_status


class VaillantBoilerTemperatureSensor(BaseVaillantTemperatureSensor):
    """Water temperature inside the boiler."""

    def __init__(self, boiler_status: BoilerStatus):
        """Initialize entity."""
        super().__init__(DOMAIN, DEVICE_CLASS_TEMPERATURE,
                         boiler_status.device_name, boiler_status.device_name)
        self._boiler_status = boiler_status

    @property
    def state(self):
        """Return the state of the entity."""
        return self._boiler_status.current_temperature

    @property
    def available(self):
        """Return True if entity is available."""
        return self._boiler_status is not None

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._boiler_status = self.hub.system.boiler_status
