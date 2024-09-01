"""Support for switch entities."""

from __future__ import annotations

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
from .entity import ThinQEntity

OPERATION_SWITCH_DESC: dict[ThinQProperty, SwitchEntityDescription] = {
    ThinQProperty.AIR_FAN_OPERATION_MODE: SwitchEntityDescription(
        key=ThinQProperty.AIR_FAN_OPERATION_MODE,
        translation_key="operation_power",
    ),
    ThinQProperty.AIR_PURIFIER_OPERATION_MODE: SwitchEntityDescription(
        key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
        translation_key="operation_power",
    ),
    ThinQProperty.BOILER_OPERATION_MODE: SwitchEntityDescription(
        key=ThinQProperty.BOILER_OPERATION_MODE,
        translation_key="operation_power",
    ),
    ThinQProperty.DEHUMIDIFIER_OPERATION_MODE: SwitchEntityDescription(
        key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
        translation_key="operation_power",
    ),
    ThinQProperty.HUMIDIFIER_OPERATION_MODE: SwitchEntityDescription(
        key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
        translation_key="operation_power",
    ),
}

DEVIE_TYPE_SWITCH_MAP: dict[DeviceType, tuple[SwitchEntityDescription, ...]] = {
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
    entities: list[ThinQSwitchEntity] = []
    for coordinator in entry.runtime_data.values():
        if (
            descriptions := DEVIE_TYPE_SWITCH_MAP.get(
                coordinator.device_api.device_type
            )
        ) is not None:
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
                    ThinQSwitchEntity(coordinator, description, prop)
                    for prop in properties
                )

    if entities:
        async_add_entities(entities)


class ThinQSwitchEntity(ThinQEntity, SwitchEntity):
    """Represent a thinq switch platform."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_is_on = self.property.get_value_as_bool()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("[%s] async_turn_on", self.name)
        await self.async_post_value("POWER_ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("[%s] async_turn_off", self.name)
        await self.async_post_value("POWER_OFF")
