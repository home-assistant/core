"""Support for switch entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import PROPERTY_WRITABLE, DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration.homeassistant.property import create_properties

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .const import POWER_OFF, POWER_ON
from .entity import PropertyInfo, ThinQEntity, ThinQEntityDescription


# Functions for switch operation.
def value_to_power_state_converter(value: Any) -> str:
    """Convert the value to string that represents power state."""
    return POWER_ON if bool(value) else POWER_OFF


@dataclass(kw_only=True, frozen=True)
class ThinQSwitchEntityDescription(ThinQEntityDescription, SwitchEntityDescription):
    """The entity description for switch."""


OPERATION_SWITCH_DESC: dict[ThinQProperty, ThinQSwitchEntityDescription] = {
    ThinQProperty.AIR_FAN_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.AIR_FAN_OPERATION_MODE,
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.AIR_FAN_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.AIR_PURIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.BOILER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.BOILER_OPERATION_MODE,
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.BOILER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.DEHUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.HUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
}

DEVIE_TYPE_SWITCH_MAP: dict[DeviceType, tuple[ThinQSwitchEntityDescription, ...]] = {
    DeviceType.AIR_PURIFIER_FAN: (
        OPERATION_SWITCH_DESC[ThinQProperty.AIR_FAN_OPERATION_MODE],
    ),
    DeviceType.AIR_PURIFIER: (
        OPERATION_SWITCH_DESC[ThinQProperty.AIR_PURIFIER_OPERATION_MODE],
    ),
    DeviceType.DEHUMIDIFIER: (
        OPERATION_SWITCH_DESC[ThinQProperty.DEHUMIDIFIER_OPERATION_MODE],
    ),
    DeviceType.HUMIDIFIER: (
        OPERATION_SWITCH_DESC[ThinQProperty.HUMIDIFIER_OPERATION_MODE],
    ),
    DeviceType.SYSTEM_BOILER: (
        OPERATION_SWITCH_DESC[ThinQProperty.BOILER_OPERATION_MODE],
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for switch platform."""
    for coordinator in entry.runtime_data.values():
        descriptions = DEVIE_TYPE_SWITCH_MAP.get(coordinator.device_api.device_type)
        if not isinstance(descriptions, tuple):
            continue

        entities: list[ThinQSwitchEntity] = []
        for description in descriptions:
            properties = create_properties(
                device_api=coordinator.device_api,
                key=description.key,
                children_keys=None,
                rw_type=PROPERTY_WRITABLE,
            )
            if not properties:
                continue

            entities.extend(
                [
                    ThinQSwitchEntity(coordinator, description, prop)
                    for prop in properties
                ]
            )

        if entities:
            async_add_entities(entities)


class ThinQSwitchEntity(ThinQEntity, SwitchEntity):
    """Represent a thinq switch platform."""

    entity_description: ThinQSwitchEntityDescription
    attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_is_on = self.property.get_value_as_bool()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("[%s] async_turn_on", self.name)
        await self.async_post_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("[%s] async_turn_off", self.name)
        await self.async_post_value(False)
