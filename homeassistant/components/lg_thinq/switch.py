"""Support for switch entities."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

DEVICE_TYPE_SWITCH_MAP: dict[DeviceType, tuple[SwitchEntityDescription, ...]] = {
    DeviceType.AIR_PURIFIER_FAN: (
        SwitchEntityDescription(
            key=ThinQProperty.AIR_FAN_OPERATION_MODE, translation_key="operation_power"
        ),
    ),
    DeviceType.AIR_PURIFIER: (
        SwitchEntityDescription(
            key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
    ),
    DeviceType.DEHUMIDIFIER: (
        SwitchEntityDescription(
            key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
    ),
    DeviceType.HUMIDIFIER: (
        SwitchEntityDescription(
            key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
    ),
    DeviceType.SYSTEM_BOILER: (
        SwitchEntityDescription(
            key=ThinQProperty.BOILER_OPERATION_MODE, translation_key="operation_power"
        ),
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
            descriptions := DEVICE_TYPE_SWITCH_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQSwitchEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQSwitchEntity(ThinQEntity, SwitchEntity):
    """Represent a thinq switch platform."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        _LOGGER.debug(
            "[%s:%s] update status: %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.is_on,
        )
        self._attr_is_on = self.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("[%s] async_turn_on", self.name)
        await self.async_call_api(self.coordinator.api.async_turn_on(self.property_id))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("[%s] async_turn_off", self.name)
        await self.async_call_api(self.coordinator.api.async_turn_off(self.property_id))
