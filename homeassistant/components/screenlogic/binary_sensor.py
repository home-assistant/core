"""Support for a ScreenLogic Binary Sensor."""
from dataclasses import dataclass
import logging

from screenlogicpy.const.common import DEVICE_TYPE, ON_OFF
from screenlogicpy.const.data import ATTR, DEVICE, GROUP, VALUE

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as SL_DOMAIN, ScreenLogicDataPath
from .coordinator import ScreenlogicDataUpdateCoordinator
from .data import (
    DEVICE_INCLUSION_RULES,
    DEVICE_SUBSCRIPTION,
    SupportedValueParameters,
    build_base_entity_description,
    iterate_expand_group_wildcard,
    preprocess_supported_values,
)
from .entity import (
    ScreenlogicEntity,
    ScreenLogicEntityDescription,
    ScreenLogicPushEntity,
    ScreenLogicPushEntityDescription,
)
from .util import cleanup_excluded_entity, generate_unique_id

_LOGGER = logging.getLogger(__name__)


@dataclass
class SupportedBinarySensorValueParameters(SupportedValueParameters):
    """Supported predefined data for a ScreenLogic binary sensor entity."""

    device_class: BinarySensorDeviceClass | None = None


SUPPORTED_DATA: list[
    tuple[ScreenLogicDataPath, SupportedValueParameters]
] = preprocess_supported_values(
    {
        DEVICE.CONTROLLER: {
            GROUP.SENSOR: {
                VALUE.ACTIVE_ALERT: SupportedBinarySensorValueParameters(),
                VALUE.CLEANER_DELAY: SupportedBinarySensorValueParameters(),
                VALUE.FREEZE_MODE: SupportedBinarySensorValueParameters(),
                VALUE.POOL_DELAY: SupportedBinarySensorValueParameters(),
                VALUE.SPA_DELAY: SupportedBinarySensorValueParameters(),
            },
        },
        DEVICE.PUMP: {
            "*": {
                VALUE.STATE: SupportedBinarySensorValueParameters(),
            },
        },
        DEVICE.INTELLICHEM: {
            GROUP.ALARM: {
                VALUE.FLOW_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.ORP_HIGH_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.ORP_LOW_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.ORP_SUPPLY_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.PH_HIGH_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.PH_LOW_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.PH_SUPPLY_ALARM: SupportedBinarySensorValueParameters(),
                VALUE.PROBE_FAULT_ALARM: SupportedBinarySensorValueParameters(),
            },
            GROUP.ALERT: {
                VALUE.ORP_LIMIT: SupportedBinarySensorValueParameters(),
                VALUE.PH_LIMIT: SupportedBinarySensorValueParameters(),
                VALUE.PH_LOCKOUT: SupportedBinarySensorValueParameters(),
            },
            GROUP.WATER_BALANCE: {
                VALUE.CORROSIVE: SupportedBinarySensorValueParameters(),
                VALUE.SCALING: SupportedBinarySensorValueParameters(),
            },
        },
        DEVICE.SCG: {
            GROUP.SENSOR: {
                VALUE.STATE: SupportedBinarySensorValueParameters(),
            },
        },
    }
)

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {DEVICE_TYPE.ALARM: BinarySensorDeviceClass.PROBLEM}


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
    data_path: ScreenLogicDataPath
    value_params: SupportedBinarySensorValueParameters
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

        entity_description_kwargs = {
            **build_base_entity_description(
                gateway, entity_key, data_path, value_data, value_params
            ),
            "device_class": SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(
                value_data.get(ATTR.DEVICE_TYPE)
            ),
        }

        if (
            sub_code := (
                value_params.subscription_code or DEVICE_SUBSCRIPTION.get(device)
            )
        ) is not None:
            entities.append(
                ScreenLogicPushBinarySensor(
                    coordinator,
                    ScreenLogicPushBinarySensorDescription(
                        subscription_code=sub_code, **entity_description_kwargs
                    ),
                )
            )
        else:
            entities.append(
                ScreenLogicBinarySensor(
                    coordinator,
                    ScreenLogicBinarySensorDescription(**entity_description_kwargs),
                )
            )

    async_add_entities(entities)


@dataclass
class ScreenLogicBinarySensorDescription(
    BinarySensorEntityDescription, ScreenLogicEntityDescription
):
    """A class that describes ScreenLogic binary sensor eneites."""


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Base class for all ScreenLogic binary sensor entities."""

    entity_description: ScreenLogicBinarySensorDescription
    _attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.entity_data[ATTR.VALUE] == ON_OFF.ON


@dataclass
class ScreenLogicPushBinarySensorDescription(
    ScreenLogicBinarySensorDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogicPushBinarySensor."""


class ScreenLogicPushBinarySensor(ScreenLogicPushEntity, ScreenLogicBinarySensor):
    """Representation of a basic ScreenLogic sensor entity."""

    entity_description: ScreenLogicPushBinarySensorDescription
