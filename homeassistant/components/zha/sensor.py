"""Sensors on Zigbee Home Automation networks."""
from __future__ import annotations

import enum
import functools
import numbers
from typing import TYPE_CHECKING, Any, Self

from zigpy import types

from homeassistant.components.climate import HVACAction
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_ANALOG_INPUT,
    CLUSTER_HANDLER_BASIC,
    CLUSTER_HANDLER_DEVICE_TEMPERATURE,
    CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
    CLUSTER_HANDLER_HUMIDITY,
    CLUSTER_HANDLER_ILLUMINANCE,
    CLUSTER_HANDLER_LEAF_WETNESS,
    CLUSTER_HANDLER_POWER_CONFIGURATION,
    CLUSTER_HANDLER_PRESSURE,
    CLUSTER_HANDLER_SMARTENERGY_METERING,
    CLUSTER_HANDLER_SOIL_MOISTURE,
    CLUSTER_HANDLER_TEMPERATURE,
    CLUSTER_HANDLER_THERMOSTAT,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import SMARTTHINGS_HUMIDITY_CLUSTER, ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

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

CLUSTER_HANDLER_ST_HUMIDITY_CLUSTER = (
    f"cluster_handler_0x{SMARTTHINGS_HUMIDITY_CLUSTER:04x}"
)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.SENSOR)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.SENSOR)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Sensor(ZhaEntity, SensorEntity):
    """Base ZHA sensor."""

    SENSOR_ATTR: int | str | None = None
    _decimals: int = 1
    _divisor: int = 1
    _multiplier: int | float = 1

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cluster_handler: ClusterHandler = cluster_handlers[0]

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        cluster_handler = cluster_handlers[0]
        if (
            cls.SENSOR_ATTR in cluster_handler.cluster.unsupported_attributes
            or cls.SENSOR_ATTR not in cluster_handler.cluster.attributes_by_name
        ):
            return None

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        assert self.SENSOR_ATTR is not None
        raw_state = self._cluster_handler.cluster.get(self.SENSOR_ATTR)
        if raw_state is None:
            return None
        return self.formatter(raw_state)

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any) -> None:
        """Handle state update from cluster handler."""
        self.async_write_ha_state()

    def formatter(self, value: int | enum.IntEnum) -> int | float | str | None:
        """Numeric pass-through formatter."""
        if self._decimals > 0:
            return round(
                float(value * self._multiplier) / self._divisor, self._decimals
            )
        return round(float(value * self._multiplier) / self._divisor)


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ANALOG_INPUT,
    manufacturers="Digi",
    stop_on_match_group=CLUSTER_HANDLER_ANALOG_INPUT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AnalogInput(Sensor):
    """Sensor that displays analog input values."""

    SENSOR_ATTR = "present_value"
    _attr_name: str = "Analog input"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_POWER_CONFIGURATION)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Battery(Sensor):
    """Battery sensor of power configuration cluster."""

    SENSOR_ATTR = "battery_percentage_remaining"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.BATTERY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name: str = "Battery"
    _attr_native_unit_of_measurement = PERCENTAGE

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Unlike any other entity, PowerConfiguration cluster may not support
        battery_percent_remaining attribute, but zha-device-handlers takes care of it
        so create the entity regardless
        """
        if zha_device.is_mains_powered:
            return None
        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    @staticmethod
    def formatter(value: int) -> int | None:
        """Return the state of the entity."""
        # per zcl specs battery percent is reported at 200% ¯\_(ツ)_/¯
        if not isinstance(value, numbers.Number) or value == -1:
            return None
        value = round(value / 2)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for battery sensors."""
        state_attrs = {}
        battery_size = self._cluster_handler.cluster.get("battery_size")
        if battery_size is not None:
            state_attrs["battery_size"] = BATTERY_SIZES.get(battery_size, "Unknown")
        battery_quantity = self._cluster_handler.cluster.get("battery_quantity")
        if battery_quantity is not None:
            state_attrs["battery_quantity"] = battery_quantity
        battery_voltage = self._cluster_handler.cluster.get("battery_voltage")
        if battery_voltage is not None:
            state_attrs["battery_voltage"] = round(battery_voltage / 10, 2)
        return state_attrs


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
    stop_on_match_group=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
    models={"VZM31-SN", "SP 234", "outletv4"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurement(Sensor):
    """Active power measurement."""

    SENSOR_ATTR = "active_power"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Active power"
    _attr_native_unit_of_measurement: str = UnitOfPower.WATT
    _div_mul_prefix = "ac_power"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for sensor."""
        attrs = {}
        if self._cluster_handler.measurement_type is not None:
            attrs["measurement_type"] = self._cluster_handler.measurement_type

        max_attr_name = f"{self.SENSOR_ATTR}_max"

        try:
            max_v = self._cluster_handler.cluster.get(max_attr_name)
        except KeyError:
            pass
        else:
            if max_v is not None:
                attrs[max_attr_name] = str(self.formatter(max_v))

        return attrs

    def formatter(self, value: int) -> int | float:
        """Return 'normalized' value."""
        multiplier = getattr(
            self._cluster_handler, f"{self._div_mul_prefix}_multiplier"
        )
        divisor = getattr(self._cluster_handler, f"{self._div_mul_prefix}_divisor")
        value = float(value * multiplier) / divisor
        if value < 100 and divisor > 1:
            return round(value, self._decimals)
        return round(value)


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
    stop_on_match_group=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PolledElectricalMeasurement(ElectricalMeasurement):
    """Polled active power measurement."""

    _attr_should_poll = True  # BaseZhaEntity defaults to False

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self.available:
            return
        await super().async_update()


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementApparentPower(
    ElectricalMeasurement, id_suffix="apparent_power"
):
    """Apparent power measurement."""

    SENSOR_ATTR = "apparent_power"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.APPARENT_POWER
    _attr_name: str = "Apparent power"
    _attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
    _div_mul_prefix = "ac_power"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementRMSCurrent(ElectricalMeasurement, id_suffix="rms_current"):
    """RMS current measurement."""

    SENSOR_ATTR = "rms_current"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CURRENT
    _attr_name: str = "RMS current"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _div_mul_prefix = "ac_current"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementRMSVoltage(ElectricalMeasurement, id_suffix="rms_voltage"):
    """RMS Voltage measurement."""

    SENSOR_ATTR = "rms_voltage"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.VOLTAGE
    _attr_name: str = "RMS voltage"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _div_mul_prefix = "ac_voltage"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementFrequency(ElectricalMeasurement, id_suffix="ac_frequency"):
    """Frequency measurement."""

    SENSOR_ATTR = "ac_frequency"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.FREQUENCY
    _attr_name: str = "AC frequency"
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _div_mul_prefix = "ac_frequency"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementPowerFactor(ElectricalMeasurement, id_suffix="power_factor"):
    """Frequency measurement."""

    SENSOR_ATTR = "power_factor"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER_FACTOR
    _attr_name: str = "Power factor"
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(
    generic_ids=CLUSTER_HANDLER_ST_HUMIDITY_CLUSTER,
    stop_on_match_group=CLUSTER_HANDLER_HUMIDITY,
)
@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_HUMIDITY,
    stop_on_match_group=CLUSTER_HANDLER_HUMIDITY,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Humidity(Sensor):
    """Humidity sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Humidity"
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_SOIL_MOISTURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SoilMoisture(Sensor):
    """Soil Moisture sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Soil moisture"
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEAF_WETNESS)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class LeafWetness(Sensor):
    """Leaf Wetness sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Leaf wetness"
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ILLUMINANCE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Illuminance(Sensor):
    """Illuminance Sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ILLUMINANCE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Illuminance"
    _attr_native_unit_of_measurement = LIGHT_LUX

    def formatter(self, value: int) -> int:
        """Convert illumination data."""
        return round(pow(10, ((value - 1) / 10000)))


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SmartEnergyMetering(Sensor):
    """Metering sensor."""

    SENSOR_ATTR: int | str = "instantaneous_demand"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Instantaneous demand"

    unit_of_measure_map = {
        0x00: UnitOfPower.WATT,
        0x01: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        0x02: UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
        0x03: f"100 {UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR}",
        0x04: f"US {UnitOfVolume.GALLONS}/{UnitOfTime.HOURS}",
        0x05: f"IMP {UnitOfVolume.GALLONS}/{UnitOfTime.HOURS}",
        0x06: UnitOfPower.BTU_PER_HOUR,
        0x07: f"l/{UnitOfTime.HOURS}",
        0x08: UnitOfPressure.KPA,  # gauge
        0x09: UnitOfPressure.KPA,  # absolute
        0x0A: f"1000 {UnitOfVolume.GALLONS}/{UnitOfTime.HOURS}",
        0x0B: "unitless",
        0x0C: f"MJ/{UnitOfTime.SECONDS}",
    }

    def formatter(self, value: int) -> int | float:
        """Pass through cluster handler formatter."""
        return self._cluster_handler.demand_formatter(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return Unit of measurement."""
        return self.unit_of_measure_map.get(self._cluster_handler.unit_of_measurement)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for battery sensors."""
        attrs = {}
        if self._cluster_handler.device_type is not None:
            attrs["device_type"] = self._cluster_handler.device_type
        if (status := self._cluster_handler.status) is not None:
            if isinstance(status, enum.IntFlag):
                attrs["status"] = str(
                    status.name if status.name is not None else status.value
                )
            else:
                attrs["status"] = str(status)[len(status.__class__.__name__) + 1 :]
        return attrs


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SmartEnergySummation(SmartEnergyMetering, id_suffix="summation_delivered"):
    """Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_summ_delivered"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_name: str = "Summation delivered"

    unit_of_measure_map = {
        0x00: UnitOfEnergy.KILO_WATT_HOUR,
        0x01: UnitOfVolume.CUBIC_METERS,
        0x02: UnitOfVolume.CUBIC_FEET,
        0x03: f"100 {UnitOfVolume.CUBIC_FEET}",
        0x04: f"US {UnitOfVolume.GALLONS}",
        0x05: f"IMP {UnitOfVolume.GALLONS}",
        0x06: "BTU",
        0x07: UnitOfVolume.LITERS,
        0x08: UnitOfPressure.KPA,  # gauge
        0x09: UnitOfPressure.KPA,  # absolute
        0x0A: f"1000 {UnitOfVolume.CUBIC_FEET}",
        0x0B: "unitless",
        0x0C: "MJ",
    }

    def formatter(self, value: int) -> int | float:
        """Numeric pass-through formatter."""
        if self._cluster_handler.unit_of_measurement != 0:
            return self._cluster_handler.summa_formatter(value)

        cooked = (
            float(self._cluster_handler.multiplier * value)
            / self._cluster_handler.divisor
        )
        return round(cooked, 3)


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"TS011F", "ZLinky_TIC"},
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PolledSmartEnergySummation(SmartEnergySummation):
    """Polled Smart Energy Metering summation sensor."""

    _attr_should_poll = True  # BaseZhaEntity defaults to False

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self.available:
            return
        await self._cluster_handler.async_force_update()


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier1SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier1_summation_delivered"
):
    """Tier 1 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier1_summ_delivered"
    _attr_name: str = "Tier 1 summation delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier2SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier2_summation_delivered"
):
    """Tier 2 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier2_summ_delivered"
    _attr_name: str = "Tier 2 summation delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier3SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier3_summation_delivered"
):
    """Tier 3 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier3_summ_delivered"
    _attr_name: str = "Tier 3 summation delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier4SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier4_summation_delivered"
):
    """Tier 4 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier4_summ_delivered"
    _attr_name: str = "Tier 4 summation delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier5SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier5_summation_delivered"
):
    """Tier 5 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier5_summ_delivered"
    _attr_name: str = "Tier 5 summation delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier6SmartEnergySummation(
    PolledSmartEnergySummation, id_suffix="tier6_summation_delivered"
):
    """Tier 6 Smart Energy Metering summation sensor."""

    SENSOR_ATTR: int | str = "current_tier6_summ_delivered"
    _attr_name: str = "Tier 6 summation delivered"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_PRESSURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Pressure(Sensor):
    """Pressure sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.PRESSURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Pressure"
    _decimals = 0
    _attr_native_unit_of_measurement = UnitOfPressure.HPA


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_TEMPERATURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Temperature(Sensor):
    """Temperature Sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.TEMPERATURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Temperature"
    _divisor = 100
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_DEVICE_TEMPERATURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DeviceTemperature(Sensor):
    """Device Temperature Sensor."""

    SENSOR_ATTR = "current_temperature"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.TEMPERATURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Device temperature"
    _divisor = 100
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC


@MULTI_MATCH(cluster_handler_names="carbon_dioxide_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class CarbonDioxideConcentration(Sensor):
    """Carbon Dioxide Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CO2
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Carbon dioxide concentration"
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(cluster_handler_names="carbon_monoxide_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class CarbonMonoxideConcentration(Sensor):
    """Carbon Monoxide Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CO
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Carbon monoxide concentration"
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(generic_ids="cluster_handler_0x042e", stop_on_match_group="voc_level")
@MULTI_MATCH(cluster_handler_names="voc_level", stop_on_match_group="voc_level")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class VOCLevel(Sensor):
    """VOC Level sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "VOC level"
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER


@MULTI_MATCH(
    cluster_handler_names="voc_level",
    models="lumi.airmonitor.acn01",
    stop_on_match_group="voc_level",
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PPBVOCLevel(Sensor):
    """VOC Level sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
    )
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "VOC level"
    _decimals = 0
    _multiplier = 1
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_BILLION


@MULTI_MATCH(cluster_handler_names="pm25")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PM25(Sensor):
    """Particulate Matter 2.5 microns or less sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.PM25
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Particulate matter"
    _decimals = 0
    _multiplier = 1
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER


@MULTI_MATCH(cluster_handler_names="formaldehyde_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class FormaldehydeConcentration(Sensor):
    """Formaldehyde Concentration sensor."""

    SENSOR_ATTR = "measured_value"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_name: str = "Formaldehyde concentration"
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ThermostatChannelSensor(Sensor):
    """All Sensors matched on Thermostatchannel need to have the same async_set_state."""

    @callback
    def async_set_state(self, *args, **kwargs) -> None:
        """Override from sensor.

        Sensor doesn't care about the arguments,
        However async_attribute_updated from Thermostat from climate.py expects a single argument.
        """
        self.async_write_ha_state()


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT,
    stop_on_match_group=CLUSTER_HANDLER_THERMOSTAT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ThermostatHVACAction(ThermostatChannelSensor, id_suffix="hvac_action"):
    """Thermostat HVAC action sensor."""

    _attr_name: str = "HVAC action"

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def native_value(self) -> str | None:
        """Return the current HVAC action."""
        if (
            self._cluster_handler.pi_heating_demand is None
            and self._cluster_handler.pi_cooling_demand is None
        ):
            return self._rm_rs_action
        return self._pi_demand_action

    @property
    def _rm_rs_action(self) -> HVACAction | None:
        """Return the current HVAC action based on running mode and running state."""

        if (running_state := self._cluster_handler.running_state) is None:
            return None

        rs_heat = (
            self._cluster_handler.RunningState.Heat_State_On
            | self._cluster_handler.RunningState.Heat_2nd_Stage_On
        )
        if running_state & rs_heat:
            return HVACAction.HEATING

        rs_cool = (
            self._cluster_handler.RunningState.Cool_State_On
            | self._cluster_handler.RunningState.Cool_2nd_Stage_On
        )
        if running_state & rs_cool:
            return HVACAction.COOLING

        running_state = self._cluster_handler.running_state
        if running_state and running_state & (
            self._cluster_handler.RunningState.Fan_State_On
            | self._cluster_handler.RunningState.Fan_2nd_Stage_On
            | self._cluster_handler.RunningState.Fan_3rd_Stage_On
        ):
            return HVACAction.FAN

        running_state = self._cluster_handler.running_state
        if running_state and running_state & self._cluster_handler.RunningState.Idle:
            return HVACAction.IDLE

        if self._cluster_handler.system_mode != self._cluster_handler.SystemMode.Off:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def _pi_demand_action(self) -> HVACAction:
        """Return the current HVAC action based on pi_demands."""

        heating_demand = self._cluster_handler.pi_heating_demand
        if heating_demand is not None and heating_demand > 0:
            return HVACAction.HEATING
        cooling_demand = self._cluster_handler.pi_cooling_demand
        if cooling_demand is not None and cooling_demand > 0:
            return HVACAction.COOLING

        if self._cluster_handler.system_mode != self._cluster_handler.SystemMode.Off:
            return HVACAction.IDLE
        return HVACAction.OFF


@MULTI_MATCH(
    cluster_handler_names={CLUSTER_HANDLER_THERMOSTAT},
    manufacturers="Sinope Technologies",
    stop_on_match_group=CLUSTER_HANDLER_THERMOSTAT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SinopeHVACAction(ThermostatHVACAction):
    """Sinope Thermostat HVAC action sensor."""

    @property
    def _rm_rs_action(self) -> HVACAction:
        """Return the current HVAC action based on running mode and running state."""

        running_mode = self._cluster_handler.running_mode
        if running_mode == self._cluster_handler.RunningMode.Heat:
            return HVACAction.HEATING
        if running_mode == self._cluster_handler.RunningMode.Cool:
            return HVACAction.COOLING

        running_state = self._cluster_handler.running_state
        if running_state and running_state & (
            self._cluster_handler.RunningState.Fan_State_On
            | self._cluster_handler.RunningState.Fan_2nd_Stage_On
            | self._cluster_handler.RunningState.Fan_3rd_Stage_On
        ):
            return HVACAction.FAN
        if (
            self._cluster_handler.system_mode != self._cluster_handler.SystemMode.Off
            and running_mode == self._cluster_handler.SystemMode.Off
        ):
            return HVACAction.IDLE
        return HVACAction.OFF


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_BASIC)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class RSSISensor(Sensor, id_suffix="rssi"):
    """RSSI sensor for a device."""

    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_device_class: SensorDeviceClass | None = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement: str | None = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = True  # BaseZhaEntity defaults to False
    _attr_name: str = "RSSI"
    unique_id_suffix: str

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        key = f"{CLUSTER_HANDLER_BASIC}_{cls.unique_id_suffix}"
        if ZHA_ENTITIES.prevent_entity_creation(Platform.SENSOR, zha_device.ieee, key):
            return None
        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return getattr(self._zha_device.device, self.unique_id_suffix)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_BASIC)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class LQISensor(RSSISensor, id_suffix="lqi"):
    """LQI sensor for a device."""

    _attr_name: str = "LQI"
    _attr_device_class = None
    _attr_native_unit_of_measurement = None


@MULTI_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class TimeLeft(Sensor, id_suffix="time_left"):
    """Sensor that displays time left value."""

    SENSOR_ATTR = "timer_time_left"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer"
    _attr_name: str = "Time left"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES


@MULTI_MATCH(cluster_handler_names="ikea_airpurifier")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class IkeaDeviceRunTime(Sensor, id_suffix="device_run_time"):
    """Sensor that displays device run time (in minutes)."""

    SENSOR_ATTR = "device_run_time"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer"
    _attr_name: str = "Device run time"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC


@MULTI_MATCH(cluster_handler_names="ikea_airpurifier")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class IkeaFilterRunTime(Sensor, id_suffix="filter_run_time"):
    """Sensor that displays run time of the current filter (in minutes)."""

    SENSOR_ATTR = "filter_run_time"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer"
    _attr_name: str = "Filter run time"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC


class AqaraFeedingSource(types.enum8):
    """Aqara pet feeder feeding source."""

    Feeder = 0x01
    HomeAssistant = 0x02


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederLastFeedingSource(Sensor, id_suffix="last_feeding_source"):
    """Sensor that displays the last feeding source of pet feeder."""

    SENSOR_ATTR = "last_feeding_source"
    _attr_name: str = "Last feeding source"
    _attr_icon = "mdi:devices"

    def formatter(self, value: int) -> int | float | None:
        """Numeric pass-through formatter."""
        return AqaraFeedingSource(value).name


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederLastFeedingSize(Sensor, id_suffix="last_feeding_size"):
    """Sensor that displays the last feeding size of the pet feeder."""

    SENSOR_ATTR = "last_feeding_size"
    _attr_name: str = "Last feeding size"
    _attr_icon: str = "mdi:counter"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederPortionsDispensed(Sensor, id_suffix="portions_dispensed"):
    """Sensor that displays the number of portions dispensed by the pet feeder."""

    SENSOR_ATTR = "portions_dispensed"
    _attr_name: str = "Portions dispensed today"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_icon: str = "mdi:counter"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederWeightDispensed(Sensor, id_suffix="weight_dispensed"):
    """Sensor that displays the weight dispensed by the pet feeder."""

    SENSOR_ATTR = "weight_dispensed"
    _attr_name: str = "Weight dispensed today"
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_icon: str = "mdi:weight-gram"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraSmokeDensityDbm(Sensor, id_suffix="smoke_density_dbm"):
    """Sensor that displays the smoke density of an Aqara smoke sensor in dB/m."""

    SENSOR_ATTR = "smoke_density_dbm"
    _attr_name: str = "Smoke density"
    _attr_native_unit_of_measurement = "dB/m"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:google-circles-communities"
    _attr_suggested_display_precision: int = 3


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PiHeatingDemand(ThermostatChannelSensor, id_suffix="pi_heating_demand"):
    """Sensor that displays the percentage of heating power used.

    Optional Thermostat attribute
    """

    SENSOR_ATTR = "pi_heating_demand"
    _attr_name: str = "Pi Heating Demand"
    _attr_icon: str = "mdi:radiator"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT


class SetpointChangeSourceEnum(types.enum8):
    """The source of the setpoint change."""

    Manual = 0x00
    Schedule = 0x01
    External = 0x02


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SetpointChangeSource(ThermostatChannelSensor, id_suffix="setpoint_change_source"):
    """Sensor that displays the source of the setpoint change.

    Optional Thermostat attribute
    """

    SENSOR_ATTR = "setpoint_change_source"
    _attr_name: str = "Setpoint Change Source"
    _attr_icon: str = "mdi:thermostat"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def formatter(self, value: int) -> str:
        """Use name of enum."""
        return SetpointChangeSourceEnum(value).name


class DanfossOpenWindowDetectionEnum(types.enum8):
    """Danfoss Open Window Detection judgments."""

    Quarantine = 0x00
    Closed = 0x01
    Maybe = 0x02
    Open = 0x03
    External = 0x04


@MULTI_MATCH(cluster_handler_names="danfoss_trv_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossOpenWindowDetection(Sensor, id_suffix="open_window_detection"):
    """Danfoss Proprietary attribute.

    Sensor that displays whether the TRV detects an open window using the temperature sensor.
    """

    SENSOR_ATTR = "open_window_detection"
    _attr_name: str = "Open Window Detection"
    _attr_icon: str = "mdi:window-open"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENUM

    def formatter(self, value: int) -> str:
        """Use name of enum."""
        return DanfossOpenWindowDetectionEnum(value).name


@MULTI_MATCH(cluster_handler_names="danfoss_trv_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossLoadEstimate(Sensor, id_suffix="load_estimate"):
    """Danfoss Proprietary attribute for communicating its estimate of the radiator load."""

    SENSOR_ATTR = "load_estimate"
    _attr_name: str = "Load Estimate"
    _attr_icon: str = "mdi:scale-balance"


@MULTI_MATCH(cluster_handler_names="danfoss_trv_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossAdaptationRunStatus(Sensor, id_suffix="adaptation_run_status"):
    """Danfoss Proprietary attribute for showing the status of the adaptation run."""

    SENSOR_ATTR = "adaptation_run_status"
    _attr_name: str = "Adaptation Run Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def formatter(self, _value: int) -> str:
        """Summary of all attributes."""
        error_code_list = [
            key for (key, elem) in self.extra_state_attributes.items() if elem
        ]

        return ", ".join(error_code_list) if error_code_list else "Nothing"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Bitmap."""
        value = self._cluster_handler.cluster.get("adaptation_run_status")
        return {
            "In Progress": bool(value & 0x0001),
            "Run Successful": bool(value & 0x0002),
            "Valve characteristic lost": bool(value & 0x0004),
        }


@MULTI_MATCH(cluster_handler_names="danfoss_trv_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossPreheatTime(Sensor, id_suffix="preheat_time"):
    """Danfoss Proprietary attribute for communicating the time when it starts pre-heating."""

    SENSOR_ATTR = "preheat_time"
    _attr_name: str = "Pre-heat Time"
    _attr_icon: str = "mdi:radiator"
    _attr_entity_registry_enabled_default = False


@MULTI_MATCH(cluster_handler_names="danfoss_trv_diagnostic_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossSoftwareErrorCode(Sensor, id_suffix="sw_error_code"):
    """Danfoss Proprietary attribute for communicating the error code."""

    SENSOR_ATTR = "sw_error_code"
    _attr_name: str = "Software Error Code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def formatter(self, _value: int) -> str:
        """Summary of all attributes."""
        error_code_list = [
            key for (key, elem) in self.extra_state_attributes.items() if elem
        ]

        return ", ".join(error_code_list) if error_code_list else "Nothing"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Bitmap."""
        value = self._cluster_handler.cluster.get("sw_error_code")
        return {
            "Top PCB sensor error": bool(value & 0x0001),
            "Side PCB sensor error": bool(value & 0x0002),
            "Non-volative Memory error": bool(value & 0x0004),
            "Unknown HW error": bool(value & 0x0008),
            # 0x0010 = N/A
            "Motor error": bool(value & 0x0020),
            # 0x0040 = N/A
            "Invalid internal communication": bool(value & 0x0080),
            # 0x0100 = N/A
            "Invalid clock information": bool(value & 0x0200),
            # 0x0400 = N/A
            "Radio communication error": bool(value & 0x0800),
            "Encoder Jammed": bool(value & 0x1000),
            "Low Battery": bool(value & 0x2000),
            "Critical Low Battery": bool(value & 0x4000),
            # 0x8000 = Reserved
        }


@MULTI_MATCH(cluster_handler_names="danfoss_trv_diagnostic_cluster")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DanfossMotorStepCounter(Sensor, id_suffix="motor_step_counter"):
    """Danfoss Proprietary attribute for communicating the motor step counter."""

    SENSOR_ATTR = "motor_step_counter"
    _attr_name: str = "Motor step counter"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
