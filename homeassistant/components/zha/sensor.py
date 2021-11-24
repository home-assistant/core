"""Sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import functools
import numbers
from typing import Any

from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
)
from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_ENERGY,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TIME_HOURS,
    TIME_SECONDS,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLOW_RATE_CUBIC_FEET_PER_MINUTE,
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
    VOLUME_GALLONS,
    VOLUME_LITERS,
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
    CHANNEL_LEAF_WETNESS,
    CHANNEL_POWER_CONFIGURATION,
    CHANNEL_PRESSURE,
    CHANNEL_SMARTENERGY_METERING,
    CHANNEL_SOIL_MOISTURE,
    CHANNEL_TEMPERATURE,
    CHANNEL_THERMOSTAT,
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
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, DOMAIN)


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
    _state_class: str | None = None
    _unit: str | None = None

    def __init__(
        self,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel: ChannelType = channels[0]

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> ZhaEntity | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        channel = channels[0]
        if cls.SENSOR_ATTR in channel.cluster.unsupported_attributes:
            return None

        return cls(unique_id, zha_device, channels, **kwargs)

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
    def state_class(self) -> str | None:
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return self._state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        return self._unit

    @property
    def native_value(self) -> StateType:
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
    _state_class = STATE_CLASS_MEASUREMENT
    _unit = PERCENTAGE
    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> ZhaEntity | None:
        """Entity Factory.

        Unlike any other entity, PowerConfiguration cluster may not support
        battery_percent_remaining attribute, but zha-device-handlers takes care of it
        so create the entity regardless
        """
        return cls(unique_id, zha_device, channels, **kwargs)

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


@MULTI_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurement(Sensor):
    """Active power measurement."""

    SENSOR_ATTR = "active_power"
    _device_class = DEVICE_CLASS_POWER
    _state_class = STATE_CLASS_MEASUREMENT
    _unit = POWER_WATT
    _div_mul_prefix = "ac_power"

    @property
    def should_poll(self) -> bool:
        """Return True if HA needs to poll for state changes."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for sensor."""
        attrs = {}
        if self._channel.measurement_type is not None:
            attrs["measurement_type"] = self._channel.measurement_type

        max_attr_name = f"{self.SENSOR_ATTR}_max"
        if (max_v := self._channel.cluster.get(max_attr_name)) is not None:
            attrs[max_attr_name] = str(self.formatter(max_v))

        return attrs

    def formatter(self, value: int) -> int | float:
        """Return 'normalized' value."""
        multiplier = getattr(self._channel, f"{self._div_mul_prefix}_multiplier")
        divisor = getattr(self._channel, f"{self._div_mul_prefix}_divisor")
        value = float(value * multiplier) / divisor
        if value < 100 and divisor > 1:
            return round(value, self._decimals)
        return round(value)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self.available:
            return
        await super().async_update()


@MULTI_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurementApparentPower(
    ElectricalMeasurement, id_suffix="apparent_power"
):
    """Apparent power measurement."""

    SENSOR_ATTR = "apparent_power"
    _device_class = DEVICE_CLASS_POWER
    _unit = POWER_VOLT_AMPERE
    _div_mul_prefix = "ac_power"

    @property
    def should_poll(self) -> bool:
        """Poll indirectly by ElectricalMeasurementSensor."""
        return False


@MULTI_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurementRMSCurrent(ElectricalMeasurement, id_suffix="rms_current"):
    """RMS current measurement."""

    SENSOR_ATTR = "rms_current"
    _device_class = DEVICE_CLASS_CURRENT
    _unit = ELECTRIC_CURRENT_AMPERE
    _div_mul_prefix = "ac_current"

    @property
    def should_poll(self) -> bool:
        """Poll indirectly by ElectricalMeasurementSensor."""
        return False


@MULTI_MATCH(channel_names=CHANNEL_ELECTRICAL_MEASUREMENT)
class ElectricalMeasurementRMSVoltage(ElectricalMeasurement, id_suffix="rms_voltage"):
    """RMS Voltage measurement."""

    SENSOR_ATTR = "rms_voltage"
    _device_class = DEVICE_CLASS_CURRENT
    _unit = ELECTRIC_POTENTIAL_VOLT
    _div_mul_prefix = "ac_voltage"

    @property
    def should_poll(self) -> bool:
        """Poll indirectly by ElectricalMeasurementSensor."""
        return False


@STRICT_MATCH(generic_ids=CHANNEL_ST_HUMIDITY_CLUSTER)
@STRICT_MATCH(channel_names=CHANNEL_HUMIDITY)
class Humidity(Sensor):
    """Humidity sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_HUMIDITY
    _divisor = 100
    _state_class = STATE_CLASS_MEASUREMENT
    _unit = PERCENTAGE


@STRICT_MATCH(channel_names=CHANNEL_SOIL_MOISTURE)
class SoilMoisture(Sensor):
    """Soil Moisture sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_HUMIDITY
    _divisor = 100
    _state_class = STATE_CLASS_MEASUREMENT
    _unit = PERCENTAGE


@STRICT_MATCH(channel_names=CHANNEL_LEAF_WETNESS)
class LeafWetness(Sensor):
    """Leaf Wetness sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_HUMIDITY
    _divisor = 100
    _state_class = STATE_CLASS_MEASUREMENT
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


@MULTI_MATCH(channel_names=CHANNEL_SMARTENERGY_METERING)
class SmartEnergyMetering(Sensor):
    """Metering sensor."""

    SENSOR_ATTR: int | str = "instantaneous_demand"
    _device_class: str | None = DEVICE_CLASS_POWER
    _state_class: str | None = STATE_CLASS_MEASUREMENT

    unit_of_measure_map = {
        0x00: POWER_WATT,
        0x01: VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        0x02: VOLUME_FLOW_RATE_CUBIC_FEET_PER_MINUTE,
        0x03: f"100 {VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR}",
        0x04: f"US {VOLUME_GALLONS}/{TIME_HOURS}",
        0x05: f"IMP {VOLUME_GALLONS}/{TIME_HOURS}",
        0x06: f"BTU/{TIME_HOURS}",
        0x07: f"l/{TIME_HOURS}",
        0x08: "kPa",  # gauge
        0x09: "kPa",  # absolute
        0x0A: f"1000 {VOLUME_GALLONS}/{TIME_HOURS}",
        0x0B: "unitless",
        0x0C: f"MJ/{TIME_SECONDS}",
    }

    def formatter(self, value: int) -> int | float:
        """Pass through channel formatter."""
        return self._channel.demand_formatter(value)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return Unit of measurement."""
        return self.unit_of_measure_map.get(self._channel.unit_of_measurement)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for battery sensors."""
        attrs = {}
        if self._channel.device_type is not None:
            attrs["device_type"] = self._channel.device_type
        if (status := self._channel.status) is not None:
            attrs["status"] = str(status)[len(status.__class__.__name__) + 1 :]
        return attrs


@MULTI_MATCH(channel_names=CHANNEL_SMARTENERGY_METERING)
class SmartEnergySummation(SmartEnergyMetering, id_suffix="summation_delivered"):
    """Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_summ_delivered"
    _device_class: str | None = DEVICE_CLASS_ENERGY
    _state_class: str = STATE_CLASS_TOTAL_INCREASING

    unit_of_measure_map = {
        0x00: ENERGY_KILO_WATT_HOUR,
        0x01: VOLUME_CUBIC_METERS,
        0x02: VOLUME_CUBIC_FEET,
        0x03: f"100 {VOLUME_CUBIC_FEET}",
        0x04: f"US {VOLUME_GALLONS}",
        0x05: f"IMP {VOLUME_GALLONS}",
        0x06: "BTU",
        0x07: VOLUME_LITERS,
        0x08: "kPa",  # gauge
        0x09: "kPa",  # absolute
        0x0A: f"1000 {VOLUME_CUBIC_FEET}",
        0x0B: "unitless",
        0x0C: "MJ",
    }

    def formatter(self, value: int) -> int | float:
        """Numeric pass-through formatter."""
        if self._channel.unit_of_measurement != 0:
            return self._channel.summa_formatter(value)

        cooked = float(self._channel.multiplier * value) / self._channel.divisor
        return round(cooked, 3)


@STRICT_MATCH(channel_names=CHANNEL_PRESSURE)
class Pressure(Sensor):
    """Pressure sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_PRESSURE
    _decimals = 0
    _state_class = STATE_CLASS_MEASUREMENT
    _unit = PRESSURE_HPA


@STRICT_MATCH(channel_names=CHANNEL_TEMPERATURE)
class Temperature(Sensor):
    """Temperature Sensor."""

    SENSOR_ATTR = "measured_value"
    _device_class = DEVICE_CLASS_TEMPERATURE
    _divisor = 100
    _state_class = STATE_CLASS_MEASUREMENT
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


@STRICT_MATCH(generic_ids="channel_0x042e")
@STRICT_MATCH(channel_names="voc_level")
class VOCLevel(Sensor):
    """VOC Level sensor."""

    SENSOR_ATTR = "measured_value"
    _decimals = 0
    _multiplier = 1e6
    _unit = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER


@STRICT_MATCH(channel_names="formaldehyde_concentration")
class FormaldehydeConcentration(Sensor):
    """Formaldehyde Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _decimals = 0
    _multiplier = 1e6
    _unit = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(channel_names=CHANNEL_THERMOSTAT)
class ThermostatHVACAction(Sensor, id_suffix="hvac_action"):
    """Thermostat HVAC action sensor."""

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> ZhaEntity | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """

        return cls(unique_id, zha_device, channels, **kwargs)

    @property
    def native_value(self) -> str | None:
        """Return the current HVAC action."""
        if (
            self._channel.pi_heating_demand is None
            and self._channel.pi_cooling_demand is None
        ):
            return self._rm_rs_action
        return self._pi_demand_action

    @property
    def _rm_rs_action(self) -> str | None:
        """Return the current HVAC action based on running mode and running state."""

        running_mode = self._channel.running_mode
        if running_mode == self._channel.RunningMode.Heat:
            return CURRENT_HVAC_HEAT
        if running_mode == self._channel.RunningMode.Cool:
            return CURRENT_HVAC_COOL

        running_state = self._channel.running_state
        if running_state and running_state & (
            self._channel.RunningState.Fan_State_On
            | self._channel.RunningState.Fan_2nd_Stage_On
            | self._channel.RunningState.Fan_3rd_Stage_On
        ):
            return CURRENT_HVAC_FAN
        if (
            self._channel.system_mode != self._channel.SystemMode.Off
            and running_mode == self._channel.SystemMode.Off
        ):
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @property
    def _pi_demand_action(self) -> str | None:
        """Return the current HVAC action based on pi_demands."""

        heating_demand = self._channel.pi_heating_demand
        if heating_demand is not None and heating_demand > 0:
            return CURRENT_HVAC_HEAT
        cooling_demand = self._channel.pi_cooling_demand
        if cooling_demand is not None and cooling_demand > 0:
            return CURRENT_HVAC_COOL

        if self._channel.system_mode != self._channel.SystemMode.Off:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @callback
    def async_set_state(self, *args, **kwargs) -> None:
        """Handle state update from channel."""
        self.async_write_ha_state()


@MULTI_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    manufacturers="Zen Within",
    stop_on_match=True,
)
class ZenHVACAction(ThermostatHVACAction):
    """Zen Within Thermostat HVAC Action."""

    @property
    def _rm_rs_action(self) -> str | None:
        """Return the current HVAC action based on running mode and running state."""

        if (running_state := self._channel.running_state) is None:
            return None

        rs_heat = (
            self._channel.RunningState.Heat_State_On
            | self._channel.RunningState.Heat_2nd_Stage_On
        )
        if running_state & rs_heat:
            return CURRENT_HVAC_HEAT

        rs_cool = (
            self._channel.RunningState.Cool_State_On
            | self._channel.RunningState.Cool_2nd_Stage_On
        )
        if running_state & rs_cool:
            return CURRENT_HVAC_COOL

        running_state = self._channel.running_state
        if running_state and running_state & (
            self._channel.RunningState.Fan_State_On
            | self._channel.RunningState.Fan_2nd_Stage_On
            | self._channel.RunningState.Fan_3rd_Stage_On
        ):
            return CURRENT_HVAC_FAN

        if self._channel.system_mode != self._channel.SystemMode.Off:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF
