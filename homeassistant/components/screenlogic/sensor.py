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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .data import (
    EntityParameter,
    PathPart,
    ScreenLogicDataRule,
    ScreenLogicEquipmentRule,
    SupportedDeviceDescriptions,
    get_ha_unit,
    process_supported_values,
)
from .entity import (
    ScreenlogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)

_LOGGER = logging.getLogger(__name__)


SUPPORTED_DATA: SupportedDeviceDescriptions = {
    DEVICE.CONTROLLER: {
        GROUP.SENSOR: {
            VALUE.AIR_TEMPERATURE: {
                EntityParameter.ENTITY_CATEGORY: None,
            },
            VALUE.ORP: {
                EntityParameter.INCLUDED: ScreenLogicEquipmentRule(
                    lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                ),
            },
            VALUE.PH: {
                EntityParameter.INCLUDED: ScreenLogicEquipmentRule(
                    lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                ),
            },
        },
    },
    DEVICE.PUMP: {
        "*": {
            VALUE.WATTS_NOW: {},
            VALUE.GPM_NOW: {
                EntityParameter.ENABLED: ScreenLogicDataRule(
                    lambda pump_data: pump_data[VALUE.TYPE] != PUMP_TYPE.INTELLIFLO_VS,
                    (PathPart.DEVICE, PathPart.INDEX),
                ),
            },
            VALUE.RPM_NOW: {
                EntityParameter.ENABLED: ScreenLogicDataRule(
                    lambda pump_data: pump_data[VALUE.TYPE] != PUMP_TYPE.INTELLIFLO_VF,
                    (PathPart.DEVICE, PathPart.INDEX),
                ),
            },
        },
    },
    DEVICE.INTELLICHEM: {
        GROUP.SENSOR: {
            VALUE.ORP_NOW: {},
            VALUE.ORP_SUPPLY_LEVEL: {
                EntityParameter.VALUE_MODIFICATION: lambda val: val - 1
            },
            VALUE.PH_NOW: {},
            VALUE.PH_PROBE_WATER_TEMP: {},
            VALUE.PH_SUPPLY_LEVEL: {
                EntityParameter.VALUE_MODIFICATION: lambda val: val - 1
            },
            VALUE.SATURATION: {},
        },
        GROUP.CONFIGURATION: {
            VALUE.CALCIUM_HARNESS: {},
            VALUE.CYA: {},
            VALUE.ORP_SETPOINT: {},
            VALUE.PH_SETPOINT: {},
            VALUE.SALT_TDS_PPM: {
                EntityParameter.INCLUDED: ScreenLogicEquipmentRule(
                    lambda flags: EQUIPMENT_FLAG.INTELLICHEM in flags
                    and EQUIPMENT_FLAG.CHLORINATOR not in flags,
                ),
            },
            VALUE.TOTAL_ALKALINITY: {},
        },
        GROUP.DOSE_STATUS: {
            VALUE.ORP_DOSING_STATE: {
                EntityParameter.VALUE_MODIFICATION: lambda val: DOSE_STATE(val).title,
            },
            VALUE.ORP_LAST_DOSE_TIME: {},
            VALUE.ORP_LAST_DOSE_VOLUME: {},
            VALUE.PH_DOSING_STATE: {
                EntityParameter.VALUE_MODIFICATION: lambda val: DOSE_STATE(val).title,
            },
            VALUE.PH_LAST_DOSE_TIME: {},
            VALUE.PH_LAST_DOSE_VOLUME: {},
        },
    },
    DEVICE.SCG: {
        GROUP.SENSOR: {
            VALUE.SALT_PPM: {},
        },
        GROUP.CONFIGURATION: {
            VALUE.SUPER_CHLOR_TIMER: {},
        },
    },
}

SL_SENSOR_VALUE_CONVERSION = {
    VALUE.ORP_SUPPLY_LEVEL: lambda val: val - 1,
    VALUE.PH_SUPPLY_LEVEL: lambda val: val - 1,
    VALUE.ORP_DOSING_STATE: lambda val: DOSE_STATE(val).title,
    VALUE.PH_DOSING_STATE: lambda val: DOSE_STATE(val).title,
}

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

    for base_kwargs, base_data in process_supported_values(
        coordinator, DOMAIN, SUPPORTED_DATA
    ):
        base_kwargs["device_class"] = SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(
            base_data.value_data.get(ATTR.DEVICE_TYPE)
        )
        base_kwargs["native_unit_of_measurement"] = get_ha_unit(base_data.value_data)
        base_kwargs["options"] = base_data.value_data.get(ATTR.ENUM_OPTIONS)
        base_kwargs["state_class"] = SL_STATE_TYPE_TO_HA_STATE_CLASS.get(
            base_data.value_data.get(ATTR.STATE_TYPE)
        )
        base_kwargs["value_mod"] = base_data.value_parameters.get(
            EntityParameter.VALUE_MODIFICATION
        )

        if base_data.subscription_code:
            entities.append(
                ScreenLogicPushSensor(
                    coordinator,
                    ScreenLogicPushSensorDescription(
                        subscription_code=base_data.subscription_code,
                        **base_kwargs,
                    ),
                )
            )
        else:
            entities.append(
                ScreenLogicSensor(
                    coordinator,
                    ScreenLogicSensorDescription(
                        **base_kwargs,
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
