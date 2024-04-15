"""Sensors on Zigbee Home Automation networks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import enum
import functools
import logging
import numbers
import random
from typing import TYPE_CHECKING, Any, Self

from zigpy import types
from zigpy.quirks.v2 import ZCLEnumMetadata, ZCLSensorMetadata
from zigpy.state import Counter, State
from zigpy.zcl.clusters.closures import WindowCovering
from zigpy.zcl.clusters.general import Basic

from homeassistant.components.climate import HVACAction
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_ANALOG_INPUT,
    CLUSTER_HANDLER_BASIC,
    CLUSTER_HANDLER_COVER,
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
    ENTITY_METADATA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.helpers import get_zha_data, validate_device_class, validate_unit
from .core.registries import SMARTTHINGS_HUMIDITY_CLUSTER, ZHA_ENTITIES
from .entity import BaseZhaEntity, ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

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

_LOGGER = logging.getLogger(__name__)

CLUSTER_HANDLER_ST_HUMIDITY_CLUSTER = (
    f"cluster_handler_0x{SMARTTHINGS_HUMIDITY_CLUSTER:04x}"
)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.SENSOR)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.SENSOR)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.SENSOR
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SENSOR]

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

    _attribute_name: int | str | None = None
    _decimals: int = 1
    _divisor: int = 1
    _multiplier: int | float = 1

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
        if ENTITY_METADATA not in kwargs and (
            cls._attribute_name in cluster_handler.cluster.unsupported_attributes
            or cls._attribute_name not in cluster_handler.cluster.attributes_by_name
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._attribute_name,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this sensor."""
        self._cluster_handler: ClusterHandler = cluster_handlers[0]
        if ENTITY_METADATA in kwargs:
            self._init_from_quirks_metadata(kwargs[ENTITY_METADATA])
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

    def _init_from_quirks_metadata(self, entity_metadata: ZCLSensorMetadata) -> None:
        """Init this entity from the quirks metadata."""
        super()._init_from_quirks_metadata(entity_metadata)
        self._attribute_name = entity_metadata.attribute_name
        if entity_metadata.divisor is not None:
            self._divisor = entity_metadata.divisor
        if entity_metadata.multiplier is not None:
            self._multiplier = entity_metadata.multiplier
        if entity_metadata.device_class is not None:
            self._attr_device_class = validate_device_class(
                SensorDeviceClass,
                entity_metadata.device_class,
                Platform.SENSOR.value,
                _LOGGER,
            )
        if entity_metadata.device_class is None and entity_metadata.unit is not None:
            self._attr_native_unit_of_measurement = validate_unit(
                entity_metadata.unit
            ).value

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        assert self._attribute_name is not None
        raw_state = self._cluster_handler.cluster.get(self._attribute_name)
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


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PollableSensor(Sensor):
    """Base ZHA sensor that polls for state."""

    _use_custom_polling: bool = True

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cancel_refresh_handle: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self._use_custom_polling:
            refresh_interval = random.randint(30, 60)
            self._cancel_refresh_handle = async_track_time_interval(
                self.hass, self._refresh, timedelta(seconds=refresh_interval)
            )
            self.debug("started polling with refresh interval of %s", refresh_interval)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        if self._cancel_refresh_handle is not None:
            self._cancel_refresh_handle()
            self._cancel_refresh_handle = None
        self.debug("stopped polling during device removal")
        await super().async_will_remove_from_hass()

    async def _refresh(self, time):
        """Call async_update at a constrained random interval."""
        if self._zha_device.available and self.hass.data[DATA_ZHA].allow_polling:
            self.debug("polling for updated state")
            await self.async_update()
            self.async_write_ha_state()
        else:
            self.debug(
                "skipping polling for updated state, available: %s, allow polled requests: %s",
                self._zha_device.available,
                self.hass.data[DATA_ZHA].allow_polling,
            )


class DeviceCounterSensor(BaseZhaEntity, SensorEntity):
    """Device counter sensor."""

    _attr_should_poll = True
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        counter_groups: str,
        counter_group: str,
        counter: str,
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        return cls(
            unique_id, zha_device, counter_groups, counter_group, counter, **kwargs
        )

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        counter_groups: str,
        counter_group: str,
        counter: str,
        **kwargs: Any,
    ) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, **kwargs)
        state: State = self._zha_device.gateway.application_controller.state
        self._zigpy_counter: Counter = (
            getattr(state, counter_groups).get(counter_group, {}).get(counter, None)
        )
        self._attr_name: str = self._zigpy_counter.name
        self.remove_future: asyncio.Future

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._zha_device.available

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        self.remove_future = self.hass.loop.create_future()
        self._zha_device.gateway.register_entity_reference(
            self._zha_device.ieee,
            self.entity_id,
            self._zha_device,
            {},
            self.device_info,
            self.remove_future,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        await super().async_will_remove_from_hass()
        self.zha_device.gateway.remove_entity_reference(self)
        self.remove_future.set_result(True)

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self._zigpy_counter.value

    async def async_update(self) -> None:
        """Retrieve latest state."""
        self.async_write_ha_state()


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class EnumSensor(Sensor):
    """Sensor with value from enum."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENUM
    _enum: type[enum.Enum]

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._attr_options = [e.name for e in self._enum]

    def _init_from_quirks_metadata(self, entity_metadata: ZCLEnumMetadata) -> None:
        """Init this entity from the quirks metadata."""
        ZhaEntity._init_from_quirks_metadata(self, entity_metadata)  # pylint: disable=protected-access
        self._attribute_name = entity_metadata.attribute_name
        self._enum = entity_metadata.enum

    def formatter(self, value: int) -> str | None:
        """Use name of enum."""
        assert self._enum is not None
        return self._enum(value).name


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_ANALOG_INPUT,
    manufacturers="Digi",
    stop_on_match_group=CLUSTER_HANDLER_ANALOG_INPUT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AnalogInput(Sensor):
    """Sensor that displays analog input values."""

    _attribute_name = "present_value"
    _attr_translation_key: str = "analog_input"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_POWER_CONFIGURATION)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Battery(Sensor):
    """Battery sensor of power configuration cluster."""

    _attribute_name = "battery_percentage_remaining"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.BATTERY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
        if not isinstance(value, numbers.Number) or value == -1 or value == 255:
            return None
        return round(value / 2)

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
class ElectricalMeasurement(PollableSensor):
    """Active power measurement."""

    _use_custom_polling: bool = False
    _attribute_name = "active_power"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement: str = UnitOfPower.WATT
    _div_mul_prefix: str | None = "ac_power"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attrs for sensor."""
        attrs = {}
        if self._cluster_handler.measurement_type is not None:
            attrs["measurement_type"] = self._cluster_handler.measurement_type

        max_attr_name = f"{self._attribute_name}_max"

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
        if self._div_mul_prefix:
            multiplier = getattr(
                self._cluster_handler, f"{self._div_mul_prefix}_multiplier"
            )
            divisor = getattr(self._cluster_handler, f"{self._div_mul_prefix}_divisor")
        else:
            multiplier = self._multiplier
            divisor = self._divisor
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

    _use_custom_polling: bool = True


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementApparentPower(PolledElectricalMeasurement):
    """Apparent power measurement."""

    _attribute_name = "apparent_power"
    _unique_id_suffix = "apparent_power"
    _use_custom_polling = False  # Poll indirectly by ElectricalMeasurementSensor
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.APPARENT_POWER
    _attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
    _div_mul_prefix = "ac_power"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementRMSCurrent(PolledElectricalMeasurement):
    """RMS current measurement."""

    _attribute_name = "rms_current"
    _unique_id_suffix = "rms_current"
    _use_custom_polling = False  # Poll indirectly by ElectricalMeasurementSensor
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _div_mul_prefix = "ac_current"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementRMSVoltage(PolledElectricalMeasurement):
    """RMS Voltage measurement."""

    _attribute_name = "rms_voltage"
    _unique_id_suffix = "rms_voltage"
    _use_custom_polling = False  # Poll indirectly by ElectricalMeasurementSensor
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _div_mul_prefix = "ac_voltage"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementFrequency(PolledElectricalMeasurement):
    """Frequency measurement."""

    _attribute_name = "ac_frequency"
    _unique_id_suffix = "ac_frequency"
    _use_custom_polling = False  # Poll indirectly by ElectricalMeasurementSensor
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.FREQUENCY
    _attr_translation_key: str = "ac_frequency"
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _div_mul_prefix = "ac_frequency"


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ElectricalMeasurementPowerFactor(PolledElectricalMeasurement):
    """Power Factor measurement."""

    _attribute_name = "power_factor"
    _unique_id_suffix = "power_factor"
    _use_custom_polling = False  # Poll indirectly by ElectricalMeasurementSensor
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = PERCENTAGE
    _div_mul_prefix = None


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

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_SOIL_MOISTURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SoilMoisture(Sensor):
    """Soil Moisture sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key: str = "soil_moisture"
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEAF_WETNESS)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class LeafWetness(Sensor):
    """Leaf Wetness sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.HUMIDITY
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key: str = "leaf_wetness"
    _divisor = 100
    _attr_native_unit_of_measurement = PERCENTAGE


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_ILLUMINANCE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Illuminance(Sensor):
    """Illuminance Sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ILLUMINANCE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    def formatter(self, value: int) -> int | None:
        """Convert illumination data."""
        if value == 0:
            return 0
        if value == 0xFFFF:
            return None
        return round(pow(10, ((value - 1) / 10000)))


@dataclass(frozen=True, kw_only=True)
class SmartEnergyMeteringEntityDescription(SensorEntityDescription):
    """Dataclass that describes a Zigbee smart energy metering entity."""

    key: str = "instantaneous_demand"
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    scale: int = 1


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SmartEnergyMetering(PollableSensor):
    """Metering sensor."""

    entity_description: SmartEnergyMeteringEntityDescription
    _use_custom_polling: bool = False
    _attribute_name = "instantaneous_demand"
    _attr_translation_key: str = "instantaneous_demand"

    _ENTITY_DESCRIPTION_MAP = {
        0x00: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        0x01: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            device_class=None,  # volume flow rate is not supported yet
        ),
        0x02: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
            device_class=None,  # volume flow rate is not supported yet
        ),
        0x03: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            device_class=None,  # volume flow rate is not supported yet
            scale=100,
        ),
        0x04: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=f"{UnitOfVolume.GALLONS}/{UnitOfTime.HOURS}",  # US gallons per hour
            device_class=None,  # volume flow rate is not supported yet
        ),
        0x05: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=f"IMP {UnitOfVolume.GALLONS}/{UnitOfTime.HOURS}",  # IMP gallons per hour
            device_class=None,  # needs to be None as imperial gallons are not supported
        ),
        0x06: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfPower.BTU_PER_HOUR,
            device_class=None,
            state_class=None,
        ),
        0x07: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=f"l/{UnitOfTime.HOURS}",
            device_class=None,  # volume flow rate is not supported yet
        ),
        0x08: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
        ),  # gauge
        0x09: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
        ),  # absolute
        0x0A: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=f"{UnitOfVolume.CUBIC_FEET}/{UnitOfTime.HOURS}",  # cubic feet per hour
            device_class=None,  # volume flow rate is not supported yet
            scale=1000,
        ),
        0x0B: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement="unitless", device_class=None, state_class=None
        ),
        0x0C: SmartEnergyMeteringEntityDescription(
            native_unit_of_measurement=f"{UnitOfEnergy.MEGA_JOULE}/{UnitOfTime.SECONDS}",
            device_class=None,  # needs to be None as MJ/s is not supported
        ),
    }

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

        entity_description = self._ENTITY_DESCRIPTION_MAP.get(
            self._cluster_handler.unit_of_measurement
        )
        if entity_description is not None:
            self.entity_description = entity_description

    def formatter(self, value: int) -> int | float:
        """Pass through cluster handler formatter."""
        return self._cluster_handler.demand_formatter(value)

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

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        state = super().native_value
        if hasattr(self, "entity_description") and state is not None:
            return float(state) * self.entity_description.scale

        return state


@dataclass(frozen=True, kw_only=True)
class SmartEnergySummationEntityDescription(SmartEnergyMeteringEntityDescription):
    """Dataclass that describes a Zigbee smart energy summation entity."""

    key: str = "summation_delivered"
    state_class: SensorStateClass | None = SensorStateClass.TOTAL_INCREASING


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SmartEnergySummation(SmartEnergyMetering):
    """Smart Energy Metering summation sensor."""

    entity_description: SmartEnergySummationEntityDescription
    _attribute_name = "current_summ_delivered"
    _unique_id_suffix = "summation_delivered"
    _attr_translation_key: str = "summation_delivered"

    _ENTITY_DESCRIPTION_MAP = {
        0x00: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        0x01: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
            device_class=SensorDeviceClass.VOLUME,
        ),
        0x02: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.CUBIC_FEET,
            device_class=SensorDeviceClass.VOLUME,
        ),
        0x03: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.CUBIC_FEET,
            device_class=SensorDeviceClass.VOLUME,
            scale=100,
        ),
        0x04: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.GALLONS,  # US gallons
            device_class=SensorDeviceClass.VOLUME,
        ),
        0x05: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=f"IMP {UnitOfVolume.GALLONS}",
            device_class=None,  # needs to be None as imperial gallons are not supported
        ),
        0x06: SmartEnergySummationEntityDescription(
            native_unit_of_measurement="BTU", device_class=None, state_class=None
        ),
        0x07: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.LITERS,
            device_class=SensorDeviceClass.VOLUME,
        ),
        0x08: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),  # gauge
        0x09: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),  # absolute
        0x0A: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfVolume.CUBIC_FEET,
            device_class=SensorDeviceClass.VOLUME,
            scale=1000,
        ),
        0x0B: SmartEnergySummationEntityDescription(
            native_unit_of_measurement="unitless", device_class=None, state_class=None
        ),
        0x0C: SmartEnergySummationEntityDescription(
            native_unit_of_measurement=UnitOfEnergy.MEGA_JOULE,
            device_class=SensorDeviceClass.ENERGY,
        ),
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
    models={"TS011F", "ZLinky_TIC", "TICMeter"},
    stop_on_match_group=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PolledSmartEnergySummation(SmartEnergySummation):
    """Polled Smart Energy Metering summation sensor."""

    _use_custom_polling: bool = True


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier1SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 1 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier1_summ_delivered"
    _unique_id_suffix = "tier1_summation_delivered"
    _attr_translation_key: str = "tier1_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier2SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 2 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier2_summ_delivered"
    _unique_id_suffix = "tier2_summation_delivered"
    _attr_translation_key: str = "tier2_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier3SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 3 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier3_summ_delivered"
    _unique_id_suffix = "tier3_summation_delivered"
    _attr_translation_key: str = "tier3_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier4SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 4 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier4_summ_delivered"
    _unique_id_suffix = "tier4_summation_delivered"
    _attr_translation_key: str = "tier4_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier5SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 5 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier5_summ_delivered"
    _unique_id_suffix = "tier5_summation_delivered"
    _attr_translation_key: str = "tier5_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
    models={"ZLinky_TIC", "TICMeter"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Tier6SmartEnergySummation(PolledSmartEnergySummation):
    """Tier 6 Smart Energy Metering summation sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_tier6_summ_delivered"
    _unique_id_suffix = "tier6_summation_delivered"
    _attr_translation_key: str = "tier6_summation_delivered"


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_SMARTENERGY_METERING,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SmartEnergySummationReceived(PolledSmartEnergySummation):
    """Smart Energy Metering summation received sensor."""

    _use_custom_polling = False  # Poll indirectly by PolledSmartEnergySummation
    _attribute_name = "current_summ_received"
    _unique_id_suffix = "summation_received"
    _attr_translation_key: str = "summation_received"

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        This attribute only started to be initialized in HA 2024.2.0,
        so the entity would be created on the first HA start after the
        upgrade for existing devices, as the initialization to see if
        an attribute is unsupported happens later in the background.
        To avoid creating unnecessary entities for existing devices,
        wait until the attribute was properly initialized once for now.
        """
        if cluster_handlers[0].cluster.get(cls._attribute_name) is None:
            return None
        return super().create_entity(unique_id, zha_device, cluster_handlers, **kwargs)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_PRESSURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Pressure(Sensor):
    """Pressure sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.PRESSURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _decimals = 0
    _attr_native_unit_of_measurement = UnitOfPressure.HPA


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_TEMPERATURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Temperature(Sensor):
    """Temperature Sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.TEMPERATURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _divisor = 100
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_DEVICE_TEMPERATURE)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DeviceTemperature(Sensor):
    """Device Temperature Sensor."""

    _attribute_name = "current_temperature"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.TEMPERATURE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key: str = "device_temperature"
    _divisor = 100
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC


@MULTI_MATCH(cluster_handler_names="carbon_dioxide_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class CarbonDioxideConcentration(Sensor):
    """Carbon Dioxide Concentration sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CO2
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(cluster_handler_names="carbon_monoxide_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class CarbonMonoxideConcentration(Sensor):
    """Carbon Monoxide Concentration sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.CO
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(generic_ids="cluster_handler_0x042e", stop_on_match_group="voc_level")
@MULTI_MATCH(cluster_handler_names="voc_level", stop_on_match_group="voc_level")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class VOCLevel(Sensor):
    """VOC Level sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
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

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
    )
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _decimals = 0
    _multiplier = 1
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_BILLION


@MULTI_MATCH(cluster_handler_names="pm25")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PM25(Sensor):
    """Particulate Matter 2.5 microns or less sensor."""

    _attribute_name = "measured_value"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.PM25
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _decimals = 0
    _multiplier = 1
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER


@MULTI_MATCH(cluster_handler_names="formaldehyde_concentration")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class FormaldehydeConcentration(Sensor):
    """Formaldehyde Concentration sensor."""

    _attribute_name = "measured_value"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_translation_key: str = "formaldehyde"
    _decimals = 0
    _multiplier = 1e6
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION


@MULTI_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT,
    stop_on_match_group=CLUSTER_HANDLER_THERMOSTAT,
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ThermostatHVACAction(Sensor):
    """Thermostat HVAC action sensor."""

    _unique_id_suffix = "hvac_action"
    _attr_translation_key: str = "hvac_action"

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
class RSSISensor(Sensor):
    """RSSI sensor for a device."""

    _attribute_name = "rssi"
    _unique_id_suffix = "rssi"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_device_class: SensorDeviceClass | None = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement: str | None = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = True  # BaseZhaEntity defaults to False
    _attr_translation_key: str = "rssi"

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
        key = f"{CLUSTER_HANDLER_BASIC}_{cls._unique_id_suffix}"
        if ZHA_ENTITIES.prevent_entity_creation(Platform.SENSOR, zha_device.ieee, key):
            return None
        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return getattr(self._zha_device.device, self._attribute_name)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_BASIC)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class LQISensor(RSSISensor):
    """LQI sensor for a device."""

    _attribute_name = "lqi"
    _unique_id_suffix = "lqi"
    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_translation_key = "lqi"


@MULTI_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class TimeLeft(Sensor):
    """Sensor that displays time left value."""

    _attribute_name = "timer_time_left"
    _unique_id_suffix = "time_left"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_translation_key: str = "timer_time_left"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES


@MULTI_MATCH(cluster_handler_names="ikea_airpurifier")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class IkeaDeviceRunTime(Sensor):
    """Sensor that displays device run time (in minutes)."""

    _attribute_name = "device_run_time"
    _unique_id_suffix = "device_run_time"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_translation_key: str = "device_run_time"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC


@MULTI_MATCH(cluster_handler_names="ikea_airpurifier")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class IkeaFilterRunTime(Sensor):
    """Sensor that displays run time of the current filter (in minutes)."""

    _attribute_name = "filter_run_time"
    _unique_id_suffix = "filter_run_time"
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.DURATION
    _attr_translation_key: str = "filter_run_time"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC


class AqaraFeedingSource(types.enum8):
    """Aqara pet feeder feeding source."""

    Feeder = 0x01
    HomeAssistant = 0x02


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederLastFeedingSource(EnumSensor):
    """Sensor that displays the last feeding source of pet feeder."""

    _attribute_name = "last_feeding_source"
    _unique_id_suffix = "last_feeding_source"
    _attr_translation_key: str = "last_feeding_source"
    _enum = AqaraFeedingSource


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederLastFeedingSize(Sensor):
    """Sensor that displays the last feeding size of the pet feeder."""

    _attribute_name = "last_feeding_size"
    _unique_id_suffix = "last_feeding_size"
    _attr_translation_key: str = "last_feeding_size"


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederPortionsDispensed(Sensor):
    """Sensor that displays the number of portions dispensed by the pet feeder."""

    _attribute_name = "portions_dispensed"
    _unique_id_suffix = "portions_dispensed"
    _attr_translation_key: str = "portions_dispensed_today"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederWeightDispensed(Sensor):
    """Sensor that displays the weight dispensed by the pet feeder."""

    _attribute_name = "weight_dispensed"
    _unique_id_suffix = "weight_dispensed"
    _attr_translation_key: str = "weight_dispensed_today"
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraSmokeDensityDbm(Sensor):
    """Sensor that displays the smoke density of an Aqara smoke sensor in dB/m."""

    _attribute_name = "smoke_density_dbm"
    _unique_id_suffix = "smoke_density_dbm"
    _attr_translation_key: str = "smoke_density"
    _attr_native_unit_of_measurement = "dB/m"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision: int = 3


class SonoffIlluminationStates(types.enum8):
    """Enum for displaying last Illumination state."""

    Dark = 0x00
    Light = 0x01


@MULTI_MATCH(cluster_handler_names="sonoff_manufacturer", models={"SNZB-06P"})
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SonoffPresenceSenorIlluminationStatus(EnumSensor):
    """Sensor that displays the illumination status the last time peresence was detected."""

    _attribute_name = "last_illumination_state"
    _unique_id_suffix = "last_illumination"
    _attr_translation_key: str = "last_illumination_state"
    _enum = SonoffIlluminationStates


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class PiHeatingDemand(Sensor):
    """Sensor that displays the percentage of heating power demanded.

    Optional thermostat attribute.
    """

    _unique_id_suffix = "pi_heating_demand"
    _attribute_name = "pi_heating_demand"
    _attr_translation_key: str = "pi_heating_demand"
    _attr_native_unit_of_measurement = PERCENTAGE
    _decimals = 0
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class SetpointChangeSourceEnum(types.enum8):
    """The source of the setpoint change."""

    Manual = 0x00
    Schedule = 0x01
    External = 0x02


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_THERMOSTAT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class SetpointChangeSource(EnumSensor):
    """Sensor that displays the source of the setpoint change.

    Optional thermostat attribute.
    """

    _unique_id_suffix = "setpoint_change_source"
    _attribute_name = "setpoint_change_source"
    _attr_translation_key: str = "setpoint_change_source"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _enum = SetpointChangeSourceEnum


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_COVER)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class WindowCoveringTypeSensor(EnumSensor):
    """Sensor that displays the type of a cover device."""

    _attribute_name: str = WindowCovering.AttributeDefs.window_covering_type.name
    _enum = WindowCovering.WindowCoveringType
    _unique_id_suffix: str = WindowCovering.AttributeDefs.window_covering_type.name
    _attr_translation_key: str = WindowCovering.AttributeDefs.window_covering_type.name
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:curtains"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_BASIC, models={"lumi.curtain.agl001"}
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraCurtainMotorPowerSourceSensor(EnumSensor):
    """Sensor that displays the power source of the Aqara E1 curtain motor device."""

    _attribute_name: str = Basic.AttributeDefs.power_source.name
    _enum = Basic.PowerSource
    _unique_id_suffix: str = Basic.AttributeDefs.power_source.name
    _attr_translation_key: str = Basic.AttributeDefs.power_source.name
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery-positive"


class AqaraE1HookState(types.enum8):
    """Aqara hook state."""

    Unlocked = 0x00
    Locked = 0x01
    Locking = 0x02
    Unlocking = 0x03


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.curtain.agl001"}
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraCurtainHookStateSensor(EnumSensor):
    """Representation of a ZHA curtain mode configuration entity."""

    _attribute_name = "hooks_state"
    _enum = AqaraE1HookState
    _unique_id_suffix = "hooks_state"
    _attr_translation_key: str = "hooks_state"
    _attr_icon: str = "mdi:hook"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
