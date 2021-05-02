"""Sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
import numbers
from typing import Any

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DOMAIN,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .core import discovery
from .core.const import (
    CHANNEL_ANALOG_INPUT,
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
)
from .core.registries import SMARTTHINGS_HUMIDITY_CLUSTER, ZHA_ENTITIES
from .core.typing import ChannelType, ZhaDeviceType
from .entity import ZhaEntity

PARALLEL_UPDATES = 5

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
            update_before_add=False,
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


class Sensor(ZhaEntity, SensorEntity):
    """Base ZHA sensor."""

    SENSOR_ATTR: int | str | None = None
    _decimals: int = 1
    _device_class: str | None = None
    _divisor: int = 1
    _multiplier: int = 1
    _unit: str | None = None

    def __init__(
        self,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel: ChannelType = channels[0]

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def device_class(self) -> str:
        """Return device class from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        return self._unit

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        assert self.SENSOR_ATTR is not None
        raw_state = self._channel.cluster.get(self.SENSOR_ATTR)
        if raw_state is None:
            return None
        return self.formatter(raw_state)

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any) -> None:
        """Handle state update from channel."""
        self.async_write_ha_state()

    def formatter(self, value: int) -> int | float:
        """Numeric pass-through formatter."""
        if self._decimals > 0:
            return round(
                float(value * self._multiplier) / self._divisor, self._decimals
            )
        return round(float(value * self._multiplier) / self._divisor)


@STRICT_MATCH(
    channel_names=CHANNEL_ANALOG_INPUT,
    manufacturers="LUMI",
    models={"lumi.plug", "lumi.plug.maus01", "lumi.plug.mmeu01"},
)
@STRICT_MATCH(channel_names=CHANNEL_ANALOG_INPUT, manufacturers="Digi")
class AnalogInput(Sensor):
    """Sensor that displays analog input values."""

    SENSOR_ATTR = "present_value"


@STRICT_MATCH(channel_names=CHANNEL_POWER_CONFIGURATION)
class Battery(Sensor):
    """Battery sensor of power configuration cluster."""

    SENSOR_ATTR = "battery_percentage_remaining"
    _device_class = DEVICE_CLASS_BATTERY
    _unit = PERCENTAGE

    @staticmethod
    def formatter(value: int) -> int:
        """Return the state of the entity."""
        # per zcl specs battery percent is reported at 200% ¯\_(ツ)_/¯
        if not isinstance(value, numbers.Number) or value == -1:
            return value
        value = round(value / 2)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for battery sensors."""
        state_attrs = {}
        battery_size = self._channel.cluster.get("battery_size")
        if battery_size is not None:
            state_attrs["battery_size"] = BATTERY_SIZES.get(battery_size, "Unknown")
        battery_quantity = self._channel.cluster.get("battery_quantity")
        if battery_quantity is not None:
            state_attrs["battery_quantity"] = battery_quantity
        battery_voltage = self._channel.cluster.get("battery_voltage")
        if battery_voltage is not None:
            state_attrs["battery_voltage"] = round(battery_voltage / 10, 2)
        return state_attrs


@STRICT_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurement(Sensor):
    """Active power measurement."""

    SENSOR_ATTR = "active_power"
    _device_class = DEVICE_CLASS_POWER
    _unit = POWER_WATT

    @property
    def should_poll(self) -> bool:
        """Return True if HA needs to poll for state changes."""
        return True

    def formatter(self, value: int) -> int | float:
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
    def formatter(value: int) -> float:
        """Convert illumination data."""
        return round(pow(10, ((value - 1) / 10000)), 1)


@STRICT_MATCH(channel_names=CHANNEL_SMARTENERGY_METERING)
class SmartEnergyMetering(Sensor):
    """Metering sensor."""

    SENSOR_ATTR = "instantaneous_demand"
    _device_class = DEVICE_CLASS_POWER

    def formatter(self, value: int) -> int | float:
        """Pass through channel formatter."""
        return self._channel.formatter_function(value)

    @property
    def unit_of_measurement(self) -> str:
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


@STRICT_MATCH(channel_names="carbon_dioxide_concentration")
class CarbonDioxideConcentration(Sensor):
    """Carbon Dioxide Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_CO2
    _decimals = 0
    _multiplier = 1e6
    _unit = CONCENTRATION_PARTS_PER_MILLION


@STRICT_MATCH(channel_names="carbon_monoxide_concentration")
class CarbonMonoxideConcentration(Sensor):
    """Carbon Monoxide Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_CO
    _decimals = 0
    _multiplier = 1e6
    _unit = CONCENTRATION_PARTS_PER_MILLION
