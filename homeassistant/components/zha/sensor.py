"""Sensors on Zigbee Home Automation networks."""
import logging

from homeassistant.core import callback
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import (
    TEMP_CELSIUS, POWER_WATT, ATTR_UNIT_OF_MEASUREMENT
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, HUMIDITY, TEMPERATURE,
    ILLUMINANCE, PRESSURE, METERING, ELECTRICAL_MEASUREMENT,
    GENERIC, SENSOR_TYPE, ATTRIBUTE_CHANNEL, ELECTRICAL_MEASUREMENT_CHANNEL,
    SIGNAL_ATTR_UPDATED, SIGNAL_STATE_ATTR)
from .entity import ZhaEntity

PARALLEL_UPDATES = 5
_LOGGER = logging.getLogger(__name__)


# Formatter functions
def pass_through_formatter(value):
    """No op update function."""
    return value


def illuminance_formatter(value):
    """Convert Illimination data."""
    if value is None:
        return None
    return round(pow(10, ((value - 1) / 10000)), 1)


def temperature_formatter(value):
    """Convert temperature data."""
    if value is None:
        return None
    return round(value / 100, 1)


def humidity_formatter(value):
    """Return the state of the entity."""
    if value is None:
        return None
    return round(float(value) / 100, 1)


def active_power_formatter(value):
    """Return the state of the entity."""
    if value is None:
        return None
    return round(float(value) / 10, 1)


def pressure_formatter(value):
    """Return the state of the entity."""
    if value is None:
        return None

    return round(float(value))


FORMATTER_FUNC_REGISTRY = {
    HUMIDITY: humidity_formatter,
    TEMPERATURE: temperature_formatter,
    PRESSURE: pressure_formatter,
    ELECTRICAL_MEASUREMENT: active_power_formatter,
    ILLUMINANCE: illuminance_formatter,
    GENERIC: pass_through_formatter,
}

UNIT_REGISTRY = {
    HUMIDITY: '%',
    TEMPERATURE: TEMP_CELSIUS,
    PRESSURE: 'hPa',
    ILLUMINANCE: 'lx',
    METERING: POWER_WATT,
    ELECTRICAL_MEASUREMENT: POWER_WATT,
    GENERIC: None
}

CHANNEL_REGISTRY = {
    ELECTRICAL_MEASUREMENT: ELECTRICAL_MEASUREMENT_CHANNEL,
}

POLLING_REGISTRY = {
    ELECTRICAL_MEASUREMENT: True
}

FORCE_UPDATE_REGISTRY = {
    ELECTRICAL_MEASUREMENT: False
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

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._sensor_type = kwargs.get(SENSOR_TYPE, GENERIC)
        self._unit = UNIT_REGISTRY.get(self._sensor_type)
        self._formatter_function = FORMATTER_FUNC_REGISTRY.get(
            self._sensor_type,
            pass_through_formatter
        )
        self._force_update = FORCE_UPDATE_REGISTRY.get(
            self._sensor_type,
            False
        )
        self._should_poll = POLLING_REGISTRY.get(
            self._sensor_type,
            False
        )
        self._channel = self.cluster_channels.get(
            CHANNEL_REGISTRY.get(self._sensor_type, ATTRIBUTE_CHANNEL)
        )

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state)
        await self.async_accept_signal(
            self._channel, SIGNAL_STATE_ATTR,
            self.async_update_state_attribute)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if self._state is None:
            return None
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    def async_set_state(self, state):
        """Handle state update from channel."""
        # this is necessary because HA saves the unit based on what shows in
        # the UI and not based on what the sensor has configured so we need
        # to flip it back after state restoration
        self._unit = UNIT_REGISTRY.get(self._sensor_type)
        self._state = self._formatter_function(state)
        self.async_schedule_update_ha_state()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state
        self._unit = last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
