"""Support for a ScreenLogic Sensor."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import DEVICE_TYPE, STATE_TYPE
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE
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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN, ScreenLogicDataPath, generate_unique_id
from .coordinator import ScreenlogicDataUpdateCoordinator
from .data import (
    DEVICE_INCLUSION_RULES,
    DEVICE_SUBSCRIPTION,
    PathPart,
    ScreenLogicDataRule,
    ScreenLogicEquipmentRule,
    SupportedValueParameters,
    cleanup_excluded_entity,
    get_ha_unit,
    iterate_expand_group_wildcard,
    preprocess_supported_values,
)
from .entity import (
    ScreenlogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SupportedSensorValueParameters(SupportedValueParameters):
    """Supported predefined data for a ScreenLogic sensor entity."""

    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    value_modification: Callable[[int], int | str] | None = lambda val: val


SUPPORTED_DATA: list[
    tuple[ScreenLogicDataPath, SupportedValueParameters]
] = preprocess_supported_values(
    {
        DEVICE.CONTROLLER: {
            GROUP.SENSOR: {
                VALUE.AIR_TEMPERATURE: SupportedSensorValueParameters(
                    device_class=SensorDeviceClass.TEMPERATURE, entity_category=None
                ),
                VALUE.ORP: SupportedSensorValueParameters(
                    included=ScreenLogicEquipmentRule(
                        lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                    )
                ),
                VALUE.PH: SupportedSensorValueParameters(
                    included=ScreenLogicEquipmentRule(
                        lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                    )
                ),
            },
        },
        DEVICE.PUMP: {
            "*": {
                VALUE.WATTS_NOW: SupportedSensorValueParameters(),
                VALUE.GPM_NOW: SupportedSensorValueParameters(
                    enabled=ScreenLogicDataRule(
                        lambda pump_data: pump_data[VALUE.TYPE]
                        != PUMP_TYPE.INTELLIFLO_VS,
                        (PathPart.DEVICE, PathPart.INDEX),
                    )
                ),
                VALUE.RPM_NOW: SupportedSensorValueParameters(
                    enabled=ScreenLogicDataRule(
                        lambda pump_data: pump_data[VALUE.TYPE]
                        != PUMP_TYPE.INTELLIFLO_VF,
                        (PathPart.DEVICE, PathPart.INDEX),
                    )
                ),
            },
        },
        DEVICE.INTELLICHEM: {
            GROUP.SENSOR: {
                VALUE.ORP_NOW: SupportedSensorValueParameters(),
                VALUE.ORP_SUPPLY_LEVEL: SupportedSensorValueParameters(
                    value_modification=lambda val: val - 1
                ),
                VALUE.PH_NOW: SupportedSensorValueParameters(),
                VALUE.PH_PROBE_WATER_TEMP: SupportedSensorValueParameters(),
                VALUE.PH_SUPPLY_LEVEL: SupportedSensorValueParameters(
                    value_modification=lambda val: val - 1
                ),
                VALUE.SATURATION: SupportedSensorValueParameters(),
            },
            GROUP.CONFIGURATION: {
                VALUE.CALCIUM_HARNESS: SupportedSensorValueParameters(),
                VALUE.CYA: SupportedSensorValueParameters(),
                VALUE.ORP_SETPOINT: SupportedSensorValueParameters(),
                VALUE.PH_SETPOINT: SupportedSensorValueParameters(),
                VALUE.SALT_TDS_PPM: SupportedSensorValueParameters(
                    included=ScreenLogicEquipmentRule(
                        lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                        and EQUIPMENT_FLAG.CHLORINATOR not in flags,
                    )
                ),
                VALUE.TOTAL_ALKALINITY: SupportedSensorValueParameters(),
            },
            GROUP.DOSE_STATUS: {
                VALUE.ORP_DOSING_STATE: SupportedSensorValueParameters(
                    value_modification=lambda val: DOSE_STATE(val).title,
                ),
                VALUE.ORP_LAST_DOSE_TIME: SupportedSensorValueParameters(),
                VALUE.ORP_LAST_DOSE_VOLUME: SupportedSensorValueParameters(),
                VALUE.PH_DOSING_STATE: SupportedSensorValueParameters(
                    value_modification=lambda val: DOSE_STATE(val).title,
                ),
                VALUE.PH_LAST_DOSE_TIME: SupportedSensorValueParameters(),
                VALUE.PH_LAST_DOSE_VOLUME: SupportedSensorValueParameters(),
            },
        },
        DEVICE.SCG: {
            GROUP.SENSOR: {
                VALUE.SALT_PPM: SupportedSensorValueParameters(),
            },
            GROUP.CONFIGURATION: {
                VALUE.SUPER_CHLOR_TIMER: SupportedSensorValueParameters(),
            },
        },
    }
)

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {
    DEVICE_TYPE.DURATION: SensorDeviceClass.DURATION,
    DEVICE_TYPE.ENUM: SensorDeviceClass.ENUM,
    DEVICE_TYPE.ENERGY: SensorDeviceClass.POWER,
    DEVICE_TYPE.POWER: SensorDeviceClass.POWER,
    DEVICE_TYPE.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    DEVICE_TYPE.VOLUME: SensorDeviceClass.VOLUME,
}

SL_STATE_TYPE_TO_HA_STATE_CLASS = {
    STATE_TYPE.MEASUREMENT: SensorStateClass.MEASUREMENT,
    STATE_TYPE.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}


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
    data_path: ScreenLogicDataPath
    value_params: SupportedSensorValueParameters
    for data_path, value_params in iterate_expand_group_wildcard(
        gateway, SUPPORTED_DATA
    ):
        entity_key = generate_unique_id(*data_path)

        device = data_path[0]

        if not (DEVICE_INCLUSION_RULES.get(device) or value_params.included).test(
            gateway, data_path
        ):
            cleanup_excluded_entity(coordinator, DOMAIN, entity_key)
            continue

        try:
            value_data = gateway.get_data(*data_path, strict=True)
        except KeyError:
            _LOGGER.debug("Failed to find %s", data_path)
            continue

        entity_kwargs = {
            "data_path": data_path,  #
            "key": entity_key,  #
            "entity_category": value_params.entity_category,
            "entity_registry_enabled_default": value_params.enabled.test(
                gateway, data_path
            ),
            "name": value_data.get(ATTR.NAME),
            "device_class": SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(
                value_data.get(ATTR.DEVICE_TYPE)
            ),
            "native_unit_of_measurement": get_ha_unit(value_data),
            "options": value_data.get(ATTR.ENUM_OPTIONS),
            "state_class": SL_STATE_TYPE_TO_HA_STATE_CLASS.get(
                value_data.get(ATTR.STATE_TYPE)
            ),
            "value_mod": value_params.value_modification,
        }

        if (
            sub_code := (
                value_params.subscription_code or DEVICE_SUBSCRIPTION.get(device)
            )
        ) is not None:
            entities.append(
                ScreenLogicPushSensor(
                    coordinator,
                    ScreenLogicPushSensorDescription(
                        subscription_code=sub_code,
                        **entity_kwargs,
                    ),
                )
            )
        else:
            entities.append(
                ScreenLogicSensor(
                    coordinator,
                    ScreenLogicSensorDescription(
                        **entity_kwargs,
                    ),
                )
            )

    async_add_entities(entities)


@dataclass
class ScreenLogicSensorMixin:
    """Mixin for SecreenLogic sensor entity."""

    value_mod: Callable[[int | str], int | str] | None = None


@dataclass
class ScreenLogicSensorDescription(
    ScreenLogicSensorMixin, SensorEntityDescription, ScreenLogicEntityDescription
):
    """Describes a ScreenLogic sensor."""


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


@dataclass
class ScreenLogicPushSensorDescription(
    ScreenLogicSensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic push sensor."""


class ScreenLogicPushSensor(ScreenLogicSensor, ScreenLogicPushEntity):
    """Representation of a ScreenLogic push sensor entity."""

    entity_description: ScreenLogicPushSensorDescription
