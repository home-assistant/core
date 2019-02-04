"""
Sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zha/
"""
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, HUMIDITY, TEMPERATURE,
    ILLUMINANCE, PRESSURE, METERING, ELECTRICAL_MEASUREMENT,
    POWER_CONFIGURATION, GENERIC, SENSOR_TYPE, LISTENER_ATTRIBUTE,
    LISTENER_ACTIVE_POWER, SIGNAL_ATTR_UPDATED, SIGNAL_STATE_ATTR)
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


# unit getters
def get_temperature_unit(sensor):
    """Get the configured temperature unit."""
    # hass is bound eager on device and lazy on entity. Use device here
    return sensor.zha_device.hass.config.units.temperature_unit


# Formatter functions
def pass_through_formatter(value, sensor):
    """No op update function."""
    return value


def temperature_formatter(value, sensor):
    """Convert temperature data."""
    from homeassistant.const import TEMP_CELSIUS
    from homeassistant.util.temperature import convert as convert_temperature
    if value is None:
        return None
    celsius = value / 100
    return round(
        convert_temperature(
            celsius,
            TEMP_CELSIUS,
            # hass is bound eager on device and lazy on entity. Use device here
            sensor.zha_device.hass.config.units.temperature_unit
        ),
        1
    )


def humidity_formatter(value, sensor):
    """Return the state of the entity."""
    if value is None:
        return None
    return round(float(value) / 100, 1)


def pressure_formatter(value, sensor):
    """Return the state of the entity."""
    if value is None:
        return None

    return round(float(value))


FORMATTER_FUNC_REGISTRY = {
    HUMIDITY: humidity_formatter,
    TEMPERATURE: temperature_formatter,
    PRESSURE: pressure_formatter,
    GENERIC: pass_through_formatter,
}

UNIT_REGISTRY = {
    HUMIDITY: '%',
    TEMPERATURE: get_temperature_unit,
    PRESSURE: 'hPa',
    ILLUMINANCE: 'lx',
    METERING: 'W',
    ELECTRICAL_MEASUREMENT: 'W',
    POWER_CONFIGURATION: '%',
    GENERIC: None
}

LISTENER_REGISTRY = {
    ELECTRICAL_MEASUREMENT: LISTENER_ACTIVE_POWER,
}

POLLING_REGISTRY = {
    ELECTRICAL_MEASUREMENT: True
}

FORCE_UPDATE_REGISTRY = {
    ELECTRICAL_MEASUREMENT: True
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation sensor from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    sensors = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if sensors is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    sensors.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA sensors."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(await make_sensor(discovery_info))

    async_add_entities(entities, update_before_add=True)


async def make_sensor(discovery_info):
    """Create ZHA sensors factory."""
    return Sensor(**discovery_info)


class Sensor(ZhaEntity):
    """Base ZHA sensor."""

    _domain = DOMAIN

    def __init__(self, unique_id, zha_device, listeners, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, listeners, **kwargs)
        sensor_type = kwargs.get(SENSOR_TYPE, GENERIC)
        unit = UNIT_REGISTRY.get(sensor_type, None)
        if callable(unit):
            unit = unit(self)
        self._unit = unit
        self._formatter_function = FORMATTER_FUNC_REGISTRY.get(
            sensor_type,
            pass_through_formatter
        )
        self._force_update = FORCE_UPDATE_REGISTRY.get(
            sensor_type,
            False
        )
        self._should_poll = POLLING_REGISTRY.get(
            sensor_type,
            False
        )
        self._listener = self.get_listener(
            LISTENER_REGISTRY.get(sensor_type, LISTENER_ATTRIBUTE)
        )

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._listener, SIGNAL_ATTR_UPDATED, self.set_state)
        await self.async_accept_signal(
            self._listener, SIGNAL_STATE_ATTR, self.update_state_attribute)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if self._state == 'unknown' or self._state is None:
            return None
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    def set_state(self, state):
        """Handle state update from listener."""
        self._state = self._formatter_function(state, self)
        self.async_schedule_update_ha_state()

    @unit_of_measurement.setter
    def unit_of_measurement(self, unit):
        """Set the unit of measurement."""
        self._unit = unit
