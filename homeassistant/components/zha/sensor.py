"""Sensors on Zigbee Home Automation networks."""
import functools
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
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.temperature import fahrenheit_to_celsius

from .core import discovery
from .core.const import (
    CHANNEL_ELECTRICAL_MEASUREMENT,
    CHANNEL_HUMIDITY,
    CHANNEL_ILLUMINANCE,
    CHANNEL_POWER_CONFIGURATION,
    CHANNEL_PRESSURE,
    CHANNEL_SMARTENERGY_METERING,
    CHANNEL_TEMPERATURE,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_STATE_ATTR,
)
from .core.registries import SMARTTHINGS_HUMIDITY_CLUSTER, ZHA_ENTITIES
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

CHANNEL_ST_HUMIDITY_CLUSTER = f"channel_0x{SMARTTHINGS_HUMIDITY_CLUSTER:04x}"
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


class Sensor(ZhaEntity):
    """Base ZHA sensor."""

    SENSOR_ATTR = None
    _decimals = 1
    _device_class = None
    _divisor = 1
    _multiplier = 1
    _unit = None

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel = channels[0]

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self._device_state_attributes.update(await self.async_state_attr_provider())

        self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )
        self.async_accept_signal(
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
        return self._state

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        if self.SENSOR_ATTR is None or self.SENSOR_ATTR != attr_name:
            return
        if value is not None:
            value = self.formatter(value)
        self._state = value
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state

    @callback
    async def async_state_attr_provider(self):
        """Initialize device state attributes."""
        return {}

    def formatter(self, value):
        """Numeric pass-through formatter."""
        if self._decimals > 0:
            return round(
                float(value * self._multiplier) / self._divisor, self._decimals
            )
        return round(float(value * self._multiplier) / self._divisor)


@STRICT_MATCH(channel_names=CHANNEL_POWER_CONFIGURATION)
class Battery(Sensor):
    """Battery sensor of power configuration cluster."""

    SENSOR_ATTR = "battery_percentage_remaining"
    _device_class = DEVICE_CLASS_BATTERY
    _unit = PERCENTAGE

    @staticmethod
    def formatter(value):
        """Return the state of the entity."""
        # per zcl specs battery percent is reported at 200% ¯\_(ツ)_/¯
        if not isinstance(value, numbers.Number) or value == -1:
            return value
        value = round(value / 2)
        return value

    async def async_state_attr_provider(self):
        """Return device state attrs for battery sensors."""
        state_attrs = {}
        attributes = ["battery_size", "battery_quantity"]
        results = await self._channel.get_attributes(attributes)
        battery_size = results.get("battery_size")
        if battery_size is not None:
            state_attrs["battery_size"] = BATTERY_SIZES.get(battery_size, "Unknown")
        battery_quantity = results.get("battery_quantity")
        if battery_quantity is not None:
            state_attrs["battery_quantity"] = battery_quantity
        return state_attrs

    @callback
    def async_update_state_attribute(self, key, value):
        """Update a single device state attribute."""
        if key == "battery_voltage":
            self._device_state_attributes[key] = round(value / 10, 1)
            self.async_write_ha_state()


@STRICT_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurement(Sensor):
    """Active power measurement."""

    SENSOR_ATTR = "active_power"
    _device_class = DEVICE_CLASS_POWER
    _divisor = 10
    _unit = POWER_WATT

    @property
    def should_poll(self) -> bool:
        """Return True if HA needs to poll for state changes."""
        return True

    def formatter(self, value) -> int:
        """Return 'normalized' value."""
        value = value * self._channel.multiplier / self._channel.divisor
        if value < 100 and self._channel.divisor > 1:
            return round(value, self._decimals)
        return round(value)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self.available:
            return
        await super().async_update()


@STRICT_MATCH(generic_ids=CHANNEL_ST_HUMIDITY_CLUSTER)
@STRICT_MATCH(channel_names=CHANNEL_HUMIDITY)
class Humidity(Sensor):
    """Humidity sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_HUMIDITY
    _divisor = 100
    _unit = PERCENTAGE


@STRICT_MATCH(channel_names=CHANNEL_ILLUMINANCE)
class Illuminance(Sensor):
    """Illuminance Sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_ILLUMINANCE
    _unit = LIGHT_LUX

    @staticmethod
    def formatter(value):
        """Convert illumination data."""
        return round(pow(10, ((value - 1) / 10000)), 1)


@STRICT_MATCH(channel_names=CHANNEL_SMARTENERGY_METERING)
class SmartEnergyMetering(Sensor):
    """Metering sensor."""

    SENSOR_ATTR = "instantaneous_demand"
    _device_class = DEVICE_CLASS_POWER

    def formatter(self, value):
        """Pass through channel formatter."""
        return self._channel.formatter_function(value)

    @property
    def unit_of_measurement(self):
        """Return Unit of measurement."""
        return self._channel.unit_of_measurement


@STRICT_MATCH(channel_names=CHANNEL_PRESSURE)
class Pressure(Sensor):
    """Pressure sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_PRESSURE
    _decimals = 0
    _unit = PRESSURE_HPA


@STRICT_MATCH(channel_names=CHANNEL_TEMPERATURE)
class Temperature(Sensor):
    """Temperature Sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_TEMPERATURE
    _divisor = 100
    _unit = TEMP_CELSIUS

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        if last_state.state == STATE_UNKNOWN:
            return
        if last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) != TEMP_CELSIUS:
            ftemp = float(last_state.state)
            self._state = round(fahrenheit_to_celsius(ftemp), 1)
            return
        self._state = last_state.state
