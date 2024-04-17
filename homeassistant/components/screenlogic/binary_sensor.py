"""Support for a ScreenLogic Binary Sensor."""

from copy import copy
import dataclasses
import logging

from screenlogicpy.const.common import ON_OFF
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
from screenlogicpy.const.msg import CODE
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
    ScreenLogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)
from .util import cleanup_excluded_entity

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScreenLogicBinarySensorDescription(
    BinarySensorEntityDescription, ScreenLogicEntityDescription
):
    """A class that describes ScreenLogic binary sensor eneites."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScreenLogicPushBinarySensorDescription(
    ScreenLogicBinarySensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogicPushBinarySensor."""


SUPPORTED_CORE_SENSORS = [
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.ACTIVE_ALERT,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.CLEANER_DELAY,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.FREEZE_MODE,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.POOL_DELAY,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.STATUS_CHANGED,
        data_root=(DEVICE.CONTROLLER, GROUP.SENSOR),
        key=VALUE.SPA_DELAY,
    ),
]

SUPPORTED_PUMP_SENSORS = [
    ScreenLogicBinarySensorDescription(
        data_root=(DEVICE.PUMP,),
        key=VALUE.STATE,
    )
]

SUPPORTED_INTELLICHEM_SENSORS = [
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.FLOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.ORP_HIGH_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.ORP_LOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.ORP_SUPPLY_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.PH_HIGH_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.PH_LOW_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.PH_SUPPLY_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALARM),
        key=VALUE.PROBE_FAULT_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALERT),
        key=VALUE.ORP_LIMIT,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALERT),
        key=VALUE.PH_LIMIT,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.ALERT),
        key=VALUE.PH_LOCKOUT,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.WATER_BALANCE),
        key=VALUE.CORROSIVE,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    ScreenLogicPushBinarySensorDescription(
        subscription_code=CODE.CHEMISTRY_CHANGED,
        data_root=(DEVICE.INTELLICHEM, GROUP.WATER_BALANCE),
        key=VALUE.SCALING,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
]

SUPPORTED_SCG_SENSORS = [
    ScreenLogicBinarySensorDescription(
        data_root=(DEVICE.SCG, GROUP.SENSOR),
        key=VALUE.STATE,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]
    gateway = coordinator.gateway

    entities: list[ScreenLogicBinarySensor] = [
        ScreenLogicPushBinarySensor(coordinator, core_sensor_description)
        for core_sensor_description in SUPPORTED_CORE_SENSORS
        if (
            gateway.get_data(
                *core_sensor_description.data_root, core_sensor_description.key
            )
            is not None
        )
    ]

    for p_index, p_data in gateway.get_data(DEVICE.PUMP).items():
        if not p_data or not p_data.get(VALUE.DATA):
            continue
        entities.extend(
            ScreenLogicPumpBinarySensor(
                coordinator, copy(proto_pump_sensor_description), p_index
            )
            for proto_pump_sensor_description in SUPPORTED_PUMP_SENSORS
        )

    chem_sensor_description: ScreenLogicPushBinarySensorDescription
    for chem_sensor_description in SUPPORTED_INTELLICHEM_SENSORS:
        chem_sensor_data_path = (
            *chem_sensor_description.data_root,
            chem_sensor_description.key,
        )
        if EQUIPMENT_FLAG.INTELLICHEM not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, DOMAIN, chem_sensor_data_path)
            continue
        if gateway.get_data(*chem_sensor_data_path):
            entities.append(
                ScreenLogicPushBinarySensor(coordinator, chem_sensor_description)
            )

    scg_sensor_description: ScreenLogicBinarySensorDescription
    for scg_sensor_description in SUPPORTED_SCG_SENSORS:
        scg_sensor_data_path = (
            *scg_sensor_description.data_root,
            scg_sensor_description.key,
        )
        if EQUIPMENT_FLAG.CHLORINATOR not in gateway.equipment_flags:
            cleanup_excluded_entity(coordinator, DOMAIN, scg_sensor_data_path)
            continue
        if gateway.get_data(*scg_sensor_data_path):
            entities.append(
                ScreenLogicBinarySensor(coordinator, scg_sensor_description)
            )

    async_add_entities(entities)


class ScreenLogicBinarySensor(ScreenLogicEntity, BinarySensorEntity):
    """Representation of a ScreenLogic binary sensor entity."""

    entity_description: ScreenLogicBinarySensorDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.entity_data[ATTR.VALUE] == ON_OFF.ON


class ScreenLogicPushBinarySensor(ScreenLogicPushEntity, ScreenLogicBinarySensor):
    """Representation of a ScreenLogic push binary sensor entity."""

    entity_description: ScreenLogicPushBinarySensorDescription


class ScreenLogicPumpBinarySensor(ScreenLogicBinarySensor):
    """Representation of a ScreenLogic binary sensor entity for pump data."""

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicBinarySensorDescription,
        pump_index: int,
    ) -> None:
        """Initialize of the entity."""
        entity_description = dataclasses.replace(
            entity_description, data_root=(DEVICE.PUMP, pump_index)
        )
        super().__init__(coordinator, entity_description)
