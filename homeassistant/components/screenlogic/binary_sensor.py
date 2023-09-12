"""Support for a ScreenLogic Binary Sensor."""
from copy import copy
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import ON_OFF
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.pump import PUMP_TYPE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
class ScreenLogicBinarySensorDescription(
    BinarySensorEntityDescription, ScreenLogicEntityDescription
):
    """A class that describes ScreenLogic binary sensor eneites."""


@dataclass
class ScreenLogicPushBinarySensorDescription(
    ScreenLogicBinarySensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogicPushBinarySensor."""


SUPPORTED_CORE_SENSORS = [
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.ACTIVE_ALERT),
        key=VALUE.ACTIVE_ALERT,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Active Alert",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.CLEANER_DELAY),
        key=VALUE.CLEANER_DELAY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Cleaner Delay",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.FREEZE_MODE),
        key=VALUE.FREEZE_MODE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Freeze Mode",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.POOL_DELAY),
        key=VALUE.POOL_DELAY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Pool Delay",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_path=(DEVICE.CONTROLLER, GROUP.SENSOR, VALUE.SPA_DELAY),
        key=VALUE.SPA_DELAY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Spa Delay",
    ),
]

SUPPORTED_PUMP_SENSORS = [
    ScreenLogicBinarySensorDescription(
        data_path=(DEVICE.PUMP, "*", VALUE.STATE),
        key="*",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="*",
    )
]

SUPPORTED_INTELLICHEM_SENSORS = [
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.FLOW_ALARM),
        key=VALUE.FLOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Flow Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.ORP_HIGH_ALARM),
        key=VALUE.ORP_HIGH_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="ORP HIGH Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.ORP_LOW_ALARM),
        key=VALUE.ORP_LOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="ORP LOW Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.ORP_SUPPLY_ALARM),
        key=VALUE.ORP_SUPPLY_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="ORP Supply Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.PH_HIGH_ALARM),
        key=VALUE.PH_HIGH_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="pH HIGH Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.PH_LOW_ALARM),
        key=VALUE.PH_LOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="pH LOW Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.PH_SUPPLY_ALARM),
        key=VALUE.PH_SUPPLY_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="pH Supply Alarm",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALARM, VALUE.PROBE_FAULT_ALARM),
        key=VALUE.PROBE_FAULT_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Probe Fault",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALERT, VALUE.ORP_LIMIT),
        key=VALUE.ORP_LIMIT,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="ORP Dose Limit Reached",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALERT, VALUE.PH_LIMIT),
        key=VALUE.PH_LIMIT,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="pH Dose Limit Reached",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.ALERT, VALUE.PH_LOCKOUT),
        key=VALUE.PH_LOCKOUT,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="pH Lockout",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.WATER_BALANCE, VALUE.CORROSIVE),
        key=VALUE.CORROSIVE,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="SI Corrosive",
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_path=(DEVICE.INTELLICHEM, GROUP.WATER_BALANCE, VALUE.SCALING),
        key=VALUE.SCALING,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="SI Scaling",
    ),
]

SUPPORTED_SCG_SENSORS = [
    ScreenLogicBinarySensorDescription(
        data_path=(DEVICE.SCG, GROUP.SENSOR, VALUE.STATE),
        key=f"{DEVICE.SCG}_{VALUE.STATE}",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Chlorinator",
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities: list[ScreenLogicBinarySensor] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
    gateway = coordinator.gateway

    entities.extend(
        [
            ScreenLogicPushBinarySensor(coordinator, core_sensor_description)
            for core_sensor_description in SUPPORTED_CORE_SENSORS
        ]
    )

    pump_sensor_description: ScreenLogicBinarySensorDescription
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
                    "Pump binary_sensor '%s' marked disabled by default",
                    pump_sensor_description.key,
                )

        entities.append(ScreenLogicBinarySensor(coordinator, pump_sensor_description))

    chem_sensor_description: ScreenLogicPushBinarySensorDescription
    for chem_sensor_description in SUPPORTED_INTELLICHEM_SENSORS:
        if EQUIPMENT_FLAG.INTELLICHEM in gateway.equipment_flags:
            entities.append(
                ScreenLogicPushBinarySensor(coordinator, chem_sensor_description)
            )
        else:
            cleanup_excluded_entity(coordinator, DOMAIN, chem_sensor_description.key)

    scg_sensor_description: ScreenLogicBinarySensorDescription
    for scg_sensor_description in SUPPORTED_SCG_SENSORS:
        if EQUIPMENT_FLAG.CHLORINATOR in gateway.equipment_flags:
            entities.append(
                ScreenLogicBinarySensor(coordinator, scg_sensor_description)
            )
        else:
            cleanup_excluded_entity(coordinator, DOMAIN, scg_sensor_description.key)

    async_add_entities(entities)


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Base class for all ScreenLogic binary sensor entities."""

    entity_description: ScreenLogicBinarySensorDescription
    _attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.entity_data[ATTR.VALUE] == ON_OFF.ON


class ScreenLogicPushBinarySensor(ScreenLogicPushEntity, ScreenLogicBinarySensor):
    """Representation of a basic ScreenLogic sensor entity."""

    entity_description: ScreenLogicPushBinarySensorDescription
