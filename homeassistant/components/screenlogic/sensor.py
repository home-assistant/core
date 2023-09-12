"""Support for a ScreenLogic Sensor."""
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import UNIT
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.chemistry import DOSE_STATE
from screenlogicpy.device_const.pump import PUMP_TYPE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import (
    ScreenlogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)
from .util import cleanup_excluded_entity, generate_unique_id

_LOGGER = logging.getLogger(__name__)


@dataclass
class ScreenLogicSensorMixin:
    """Mixin for SecreenLogic sensor entity."""

    value_mod: Callable[[int | str], int | str] | None = None


@dataclass
class ScreenLogicSensorDescription(
    ScreenLogicSensorMixin, SensorEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic sensor."""


@dataclass
class ScreenLogicPushSensorDescription(
    ScreenLogicSensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic push sensor."""


SUPPORTED_CORE_SENSORS = [
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.AIR_TEMPERATURE),
        key=VALUE.AIR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="*",
        state_class=SensorStateClass.MEASUREMENT,
        name="Air Temperature",
    ),
]

SUPPORTED_PUMP_SENSORS = [
    ScreenLogicSensorDescription(
        data_path=(DEVICE.PUMP, "*", VALUE.WATTS_NOW),
        key="*",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        name="*",
    ),
    ScreenLogicSensorDescription(
        data_path=(DEVICE.PUMP, "*", VALUE.GPM_NOW),
        key="*",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="gpm",
        state_class=SensorStateClass.MEASUREMENT,
        name="*",
    ),
    ScreenLogicSensorDescription(
        data_path=(DEVICE.PUMP, "*", VALUE.RPM_NOW),
        key="*",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        name="*",
    ),
]

SUPPORTED_INTELLICHEM_SENSORS = [
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.ORP),
        key=VALUE.ORP,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        name="ORP",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.PH),
        key=VALUE.PH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="pH",
        state_class=SensorStateClass.MEASUREMENT,
        name="pH",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.ORP_NOW),
        key=VALUE.ORP_NOW,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        name="ORP Now",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.PH_NOW),
        key=VALUE.PH_NOW,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="pH",
        state_class=SensorStateClass.MEASUREMENT,
        name="pH Now",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.ORP_SUPPLY_LEVEL),
        key=VALUE.ORP_SUPPLY_LEVEL,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        name="ORP Supply Level",
        value_mod=lambda value: int(value) - 1,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.PH_SUPPLY_LEVEL),
        key=VALUE.PH_SUPPLY_LEVEL,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        name="pH Supply Level",
        value_mod=lambda value: int(value) - 1,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.PH_PROBE_WATER_TEMP),
        key=VALUE.PH_PROBE_WATER_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="*",
        state_class=SensorStateClass.MEASUREMENT,
        name="pH Probe Water Temperature",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.SENSOR, VALUE.SATURATION),
        key=VALUE.SATURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="lsi",
        state_class=SensorStateClass.MEASUREMENT,
        name="Saturation Index",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.CALCIUM_HARNESS),
        key=VALUE.CALCIUM_HARNESS,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Calcium Hardness",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.CYA),
        key=VALUE.CYA,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Cyanuric Acid",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.ORP_SETPOINT),
        key=VALUE.ORP_SETPOINT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        name="ORP Setpoint",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.PH_SETPOINT),
        key=VALUE.PH_SETPOINT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="pH",
        name="pH Setpoint",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.TOTAL_ALKALINITY),
        key=VALUE.TOTAL_ALKALINITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Total Alkalinity",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION, VALUE.SALT_TDS_PPM),
        key=VALUE.SALT_TDS_PPM,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Salt/TDS",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.ORP_DOSING_STATE),
        key=VALUE.ORP_DOSING_STATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        name="ORP Dosing State",
        options=["Dosing", "Mixing", "Monitoring"],
        value_mod=lambda value: DOSE_STATE(value).title,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.ORP_LAST_DOSE_TIME),
        key=VALUE.ORP_LAST_DOSE_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Last ORP Dose Time",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.ORP_LAST_DOSE_VOLUME),
        key=VALUE.ORP_LAST_DOSE_VOLUME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement="mL",
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Last ORP Dose Volume",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.PH_DOSING_STATE),
        key=VALUE.PH_DOSING_STATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        name="pH Dosing State",
        options=["Dosing", "Mixing", "Monitoring"],
        value_mod=lambda value: DOSE_STATE(value).title,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.PH_LAST_DOSE_TIME),
        key=VALUE.PH_LAST_DOSE_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Last pH Dose Time",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS, VALUE.PH_LAST_DOSE_VOLUME),
        key=VALUE.PH_LAST_DOSE_VOLUME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement="mL",
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Last pH Dose Volume",
    ),
]

SUPPORTED_SCG_SENSORS = [
    ScreenLogicSensorDescription(
        data_path=(DEVICE.SCG, GROUP.SENSOR, VALUE.SALT_PPM),
        key=f"{DEVICE.SCG}_{VALUE.SALT_PPM}",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        name="Chlorinator Salt",
    ),
    ScreenLogicSensorDescription(
        data_path=(DEVICE.SCG, GROUP.CONFIGURATION, VALUE.SUPER_CHLOR_TIMER),
        key=VALUE.SUPER_CHLOR_TIMER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        name="Super Chlorination Timer",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicSensor] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
    gateway = coordinator.gateway

    sl_temp_unit = (
        UnitOfTemperature.CELSIUS
        if gateway.temperature_unit == UNIT.CELSIUS
        else UnitOfTemperature.FAHRENHEIT
    )

    core_sensor_description: ScreenLogicPushSensorDescription
    for core_sensor_description in SUPPORTED_CORE_SENSORS:
        if core_sensor_description.device_class == SensorDeviceClass.TEMPERATURE:
            core_sensor_description.native_unit_of_measurement = sl_temp_unit
        entities.append(ScreenLogicPushSensor(coordinator, core_sensor_description))

    pump_sensor_description: ScreenLogicSensorDescription
    for pnum, pdata in gateway.get_data(DEVICE.PUMP).items():
        if pdata[VALUE.DATA] == 0:
            continue
        pump_type = pdata[VALUE.TYPE]
        for proto_pump_sensor_description in SUPPORTED_PUMP_SENSORS:
            pump_sensor_description = copy(proto_pump_sensor_description)
            device, group, value = pump_sensor_description.data_path
            group = int(pnum)
            pump_sensor_description.data_path = (device, group, value)
            pump_sensor_description.key = generate_unique_id(device, group, value)
            pump_sensor_description.name = pdata[value][ATTR.NAME]
            if (value == VALUE.GPM_NOW and pump_type == PUMP_TYPE.INTELLIFLO_VS) or (
                value == VALUE.RPM_NOW and pump_type == PUMP_TYPE.INTELLIFLO_VF
            ):
                pump_sensor_description.entity_registry_enabled_default = False
                _LOGGER.debug(
                    "Pump sensor '%s' marked disabled by default",
                    pump_sensor_description.key,
                )

            entities.append(ScreenLogicSensor(coordinator, pump_sensor_description))

    chem_sensor_description: ScreenLogicPushSensorDescription
    for chem_sensor_description in SUPPORTED_INTELLICHEM_SENSORS:
        if EQUIPMENT_FLAG.INTELLICHEM in gateway.equipment_flags:
            if chem_sensor_description.device_class == SensorDeviceClass.TEMPERATURE:
                chem_sensor_description.native_unit_of_measurement = sl_temp_unit
            entities.append(ScreenLogicPushSensor(coordinator, chem_sensor_description))
        else:
            cleanup_excluded_entity(coordinator, DOMAIN, chem_sensor_description.key)

    scg_sensor_description: ScreenLogicSensorDescription
    for scg_sensor_description in SUPPORTED_SCG_SENSORS:
        if EQUIPMENT_FLAG.CHLORINATOR in gateway.equipment_flags:
            entities.append(ScreenLogicSensor(coordinator, scg_sensor_description))
        else:
            cleanup_excluded_entity(coordinator, DOMAIN, scg_sensor_description.key)

    async_add_entities(entities)


class ScreenLogicSensor(ScreenlogicEntity, SensorEntity):
    """Representation of a ScreenLogic sensor entity."""

    entity_description: ScreenLogicSensorDescription
    _attr_has_entity_name = True

    @property
    def native_value(self) -> str | int | float:
        """State of the sensor."""
        val = self.entity_data[ATTR.VALUE]
        value_mod = self.entity_description.value_mod
        return value_mod(val) if value_mod else val


class ScreenLogicPushSensor(ScreenLogicSensor, ScreenLogicPushEntity):
    """Representation of a ScreenLogic push sensor entity."""

    entity_description: ScreenLogicPushSensorDescription
