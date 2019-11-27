"""Sensors on Zigbee Home Automation networks."""
import logging
import numbers

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DOMAIN,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, POWER_WATT, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core.const import (
    CHANNEL_ATTRIBUTE,
    CHANNEL_ELECTRICAL_MEASUREMENT,
    CHANNEL_POWER_CONFIGURATION,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SENSOR_BATTERY,
    SENSOR_ELECTRICAL_MEASUREMENT,
    SENSOR_GENERIC,
    SENSOR_HUMIDITY,
    SENSOR_ILLUMINANCE,
    SENSOR_METERING,
    SENSOR_PRESSURE,
    SENSOR_TEMPERATURE,
    SENSOR_TYPE,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_STATE_ATTR,
    UNKNOWN,
    ZHA_DISCOVERY_NEW,
)
from .entity import ZhaEntity

PARALLEL_UPDATES = 5
_LOGGER = logging.getLogger(__name__)

BATTERY_SIZES = {
    0: "No battery",
    1: "Built in",
    2: "Other",
    3: "AA",
    4: "AAA",
    5: "C",
    6: "D",
    7: "CR2",
    8: "CR123A",
    9: "CR2450",
    10: "CR2032",
    11: "CR1632",
    255: "Unknown",
}


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


def battery_percentage_remaining_formatter(value):
    """Return the state of the entity."""
    # per zcl specs battery percent is reported at 200% ¯\_(ツ)_/¯
    if not isinstance(value, numbers.Number) or value == -1:
        return value
    value = value / 2
    value = int(round(value))
    return value


async def async_battery_device_state_attr_provider(channel):
    """Return device statr attrs for battery sensors."""
    state_attrs = {}
    battery_size = await channel.get_attribute_value("battery_size")
    if battery_size is not None:
        state_attrs["battery_size"] = BATTERY_SIZES.get(battery_size, "Unknown")
    battery_quantity = await channel.get_attribute_value("battery_quantity")
    if battery_quantity is not None:
        state_attrs["battery_quantity"] = battery_quantity
    return state_attrs


FORMATTER_FUNC_REGISTRY = {
    SENSOR_HUMIDITY: humidity_formatter,
    SENSOR_TEMPERATURE: temperature_formatter,
    SENSOR_PRESSURE: pressure_formatter,
    SENSOR_ELECTRICAL_MEASUREMENT: active_power_formatter,
    SENSOR_ILLUMINANCE: illuminance_formatter,
    SENSOR_GENERIC: pass_through_formatter,
    SENSOR_BATTERY: battery_percentage_remaining_formatter,
}

UNIT_REGISTRY = {
    SENSOR_HUMIDITY: "%",
    SENSOR_TEMPERATURE: TEMP_CELSIUS,
    SENSOR_PRESSURE: "hPa",
    SENSOR_ILLUMINANCE: "lx",
    SENSOR_ELECTRICAL_MEASUREMENT: POWER_WATT,
    SENSOR_GENERIC: None,
    SENSOR_BATTERY: "%",
}

CHANNEL_REGISTRY = {
    SENSOR_ELECTRICAL_MEASUREMENT: CHANNEL_ELECTRICAL_MEASUREMENT,
    SENSOR_BATTERY: CHANNEL_POWER_CONFIGURATION,
}

POLLING_REGISTRY = {SENSOR_ELECTRICAL_MEASUREMENT: True}

FORCE_UPDATE_REGISTRY = {SENSOR_ELECTRICAL_MEASUREMENT: False}

DEVICE_CLASS_REGISTRY = {
    UNKNOWN: None,
    SENSOR_HUMIDITY: DEVICE_CLASS_HUMIDITY,
    SENSOR_TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
    SENSOR_PRESSURE: DEVICE_CLASS_PRESSURE,
    SENSOR_ILLUMINANCE: DEVICE_CLASS_ILLUMINANCE,
    SENSOR_METERING: DEVICE_CLASS_POWER,
    SENSOR_ELECTRICAL_MEASUREMENT: DEVICE_CLASS_POWER,
    SENSOR_BATTERY: DEVICE_CLASS_BATTERY,
}


DEVICE_STATE_ATTR_PROVIDER_REGISTRY = {
    SENSOR_BATTERY: async_battery_device_state_attr_provider
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up Zigbee Home Automation sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation sensor from config entry."""

    async def async_discover(discovery_info):
        await _async_setup_entities(
            hass, config_entry, async_add_entities, [discovery_info]
        )

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    sensors = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if sensors is not None:
        await _async_setup_entities(
            hass, config_entry, async_add_entities, sensors.values()
        )
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(
    hass, config_entry, async_add_entities, discovery_infos
):
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
        self._sensor_type = kwargs.get(SENSOR_TYPE, SENSOR_GENERIC)
        self._channel = self.cluster_channels.get(
            CHANNEL_REGISTRY.get(self._sensor_type, CHANNEL_ATTRIBUTE)
        )
        if self._sensor_type == SENSOR_METERING:
            self._unit = self._channel.unit_of_measurement
            self._formatter_function = self._channel.formatter_function
        else:
            self._unit = UNIT_REGISTRY.get(self._sensor_type)
            self._formatter_function = FORMATTER_FUNC_REGISTRY.get(
                self._sensor_type, pass_through_formatter
            )
        self._force_update = FORCE_UPDATE_REGISTRY.get(self._sensor_type, False)
        self._should_poll = POLLING_REGISTRY.get(self._sensor_type, False)
        self._device_class = DEVICE_CLASS_REGISTRY.get(self._sensor_type, None)
        self.state_attr_provider = DEVICE_STATE_ATTR_PROVIDER_REGISTRY.get(
            self._sensor_type, None
        )

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self.state_attr_provider is not None:
            self._device_state_attributes = await self.state_attr_provider(
                self._channel
            )
        await self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )
        await self.async_accept_signal(
            self._channel, SIGNAL_STATE_ATTR, self.async_update_state_attribute
        )

    @property
    def device_class(self) -> str:
        """Return device class from component DEVICE_CLASSES."""
        return self._device_class

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
        if self._sensor_type == SENSOR_METERING:
            self._unit = self._channel.unit_of_measurement
        else:
            self._unit = UNIT_REGISTRY.get(self._sensor_type)
        self._state = self._formatter_function(state)
        self.async_schedule_update_ha_state()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state
        self._unit = last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
