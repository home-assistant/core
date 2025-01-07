"""Support for a ScreenLogic Sensor."""

from collections.abc import Callable
from copy import copy
import dataclasses
import logging

from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.chemistry import DOSE_STATE
from screenlogicpy.device_const.pump import PUMP_TYPE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import (
    ScreenLogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)
from .types import ScreenLogicConfigEntry
from .util import cleanup_excluded_entity, get_ha_unit

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScreenLogicSensorDescription(
    SensorEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic sensor."""

    value_mod: Callable[[int | str], int | str] | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScreenLogicPushSensorDescription(
    ScreenLogicSensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic push sensor."""


SUPPORTED_CORE_SENSORS = [
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.AIR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="air_temperature",
    ),
]

SUPPORTED_PUMP_SENSORS = [
    ScreenLogicSensorDescription(
        data_root=(DEVICE.PUMP,),
        key=VALUE.WATTS_NOW,
        device_class=SensorDeviceClass.POWER,
    ),
    ScreenLogicSensorDescription(
        data_root=(DEVICE.PUMP,),
        key=VALUE.GPM_NOW,
        enabled_lambda=lambda type: type != PUMP_TYPE.INTELLIFLO_VS,
    ),
    ScreenLogicSensorDescription(
        data_root=(DEVICE.PUMP,),
        key=VALUE.RPM_NOW,
        enabled_lambda=lambda type: type != PUMP_TYPE.INTELLIFLO_VF,
    ),
]

SUPPORTED_INTELLICHEM_SENSORS = [
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.ORP,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.ORP_NOW,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="chem_now",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.PH_NOW,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="chem_now",
        translation_placeholders={"chem": "pH"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.ORP_SUPPLY_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        value_mod=lambda val: int(val) - 1,
        translation_key="chem_supply_level",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.PH_SUPPLY_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        value_mod=lambda val: int(val) - 1,
        translation_key="chem_supply_level",
        translation_placeholders={"chem": "pH"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.PH_PROBE_WATER_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="ph_probe_water_temp",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.SENSOR),
        key=VALUE.SATURATION,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="saturation",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.CALCIUM_HARDNESS,
        entity_registry_enabled_default=False,  # Superseded by number entity
        translation_key="calcium_hardness",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.CYA,
        entity_registry_enabled_default=False,  # Superseded by number entity
        translation_key="cya",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.ORP_SETPOINT,
        translation_key="chem_setpoint",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.PH_SETPOINT,
        translation_key="chem_setpoint",
        translation_placeholders={"chem": "pH"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.TOTAL_ALKALINITY,
        entity_registry_enabled_default=False,  # Superseded by number entity
        translation_key="total_alkalinity",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.CONFIGURATION),
        key=VALUE.SALT_TDS_PPM,
        entity_registry_enabled_default=False,  # Superseded by number entity
        translation_key="salt_tds_ppm",
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.ORP_DOSING_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=["dosing", "mixing", "monitoring"],
        value_mod=lambda val: DOSE_STATE(val).name.lower(),
        translation_key="chem_dose_state",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.ORP_LAST_DOSE_TIME,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="chem_last_dose_time",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.ORP_LAST_DOSE_VOLUME,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="chem_last_dose_volume",
        translation_placeholders={"chem": "ORP"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.PH_DOSING_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=["dosing", "mixing", "monitoring"],
        value_mod=lambda val: DOSE_STATE(val).name.lower(),
        translation_key="chem_dose_state",
        translation_placeholders={"chem": "pH"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.PH_LAST_DOSE_TIME,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="chem_last_dose_time",
        translation_placeholders={"chem": "pH"},
    ),
    ScreenLogicPushSensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.DOSE_STATUS),
        key=VALUE.PH_LAST_DOSE_VOLUME,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="chem_last_dose_volume",
        translation_placeholders={"chem": "pH"},
    ),
]

SUPPORTED_SCG_SENSORS = [
    ScreenLogicSensorDescription(
        data_root=(DEVICE.SCG, GROUP.SENSOR),
        key=VALUE.SALT_PPM,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="salt_ppm",
    ),
    ScreenLogicSensorDescription(
        data_root=(DEVICE.SCG, GROUP.CONFIGURATION),
        key=VALUE.SUPER_CHLOR_TIMER,
        translation_key="super_chlor_timer",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ScreenLogicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator = config_entry.runtime_data
    gateway = coordinator.gateway

    entities: list[ScreenLogicSensor] = [
        ScreenLogicPushSensor(coordinator, core_sensor_description)
        for core_sensor_description in SUPPORTED_CORE_SENSORS
        if (
            gateway.get_data(
                *core_sensor_description.data_root, core_sensor_description.key
            )
            is not None
        )
    ]

    for pump_index, pump_data in gateway.get_data(DEVICE.PUMP).items():
        if not pump_data or not pump_data.get(VALUE.DATA):
            continue
        pump_type = pump_data[VALUE.TYPE]
        for proto_pump_sensor_description in SUPPORTED_PUMP_SENSORS:
            if not pump_data.get(proto_pump_sensor_description.key):
                continue
            entities.append(
                ScreenLogicPumpSensor(
                    coordinator,
                    copy(proto_pump_sensor_description),
                    pump_index,
                    pump_type,
                )
            )

    chem_sensor_description: ScreenLogicPushSensorDescription
    for chem_sensor_description in SUPPORTED_INTELLICHEM_SENSORS:
        chem_sensor_data_path = (
            *chem_sensor_description.data_root,
            chem_sensor_description.key,
        )
        if EQUIPMENT_FLAG.INTELLICHEM not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, SENSOR_DOMAIN, chem_sensor_data_path)
            continue
        if gateway.get_data(*chem_sensor_data_path):
            chem_sensor_description = dataclasses.replace(
                chem_sensor_description, entity_category=EntityCategory.DIAGNOSTIC
            )
            entities.append(ScreenLogicPushSensor(coordinator, chem_sensor_description))

    scg_sensor_description: ScreenLogicSensorDescription
    for scg_sensor_description in SUPPORTED_SCG_SENSORS:
        scg_sensor_data_path = (
            *scg_sensor_description.data_root,
            scg_sensor_description.key,
        )
        if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, SENSOR_DOMAIN, scg_sensor_data_path)
            continue
        if gateway.get_data(*scg_sensor_data_path):
            scg_sensor_description = dataclasses.replace(
                scg_sensor_description, entity_category=EntityCategory.DIAGNOSTIC
            )
            entities.append(ScreenLogicSensor(coordinator, scg_sensor_description))

    async_add_entities(entities)


class ScreenLogicSensor(ScreenLogicEntity, SensorEntity):
    """Representation of a ScreenLogic sensor entity."""

    entity_description: ScreenLogicSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicSensorDescription,
    ) -> None:
        """Initialize of the entity."""
        super().__init__(coordinator, entity_description)
        self._attr_native_unit_of_measurement = get_ha_unit(
            self.entity_data.get(ATTR.UNIT)
        )

    @property
    def native_value(self) -> str | int | float:
        """State of the sensor."""
        val = self.entity_data[ATTR.VALUE]
        value_mod = self.entity_description.value_mod
        return value_mod(val) if value_mod else val


class ScreenLogicPushSensor(ScreenLogicSensor, ScreenLogicPushEntity):
    """Representation of a ScreenLogic push sensor entity."""

    entity_description: ScreenLogicPushSensorDescription


class ScreenLogicPumpSensor(ScreenLogicSensor):
    """Representation of a ScreenLogic pump sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicSensorDescription,
        pump_index: int,
        pump_type: int,
    ) -> None:
        """Initialize of the entity."""
        entity_description = dataclasses.replace(
            entity_description, data_root=(DEVICE.PUMP, pump_index)
        )
        super().__init__(coordinator, entity_description)
        if entity_description.enabled_lambda:
            self._attr_entity_registry_enabled_default = (
                entity_description.enabled_lambda(pump_type)
            )
