"""Support for switch entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQSwitchEntityDescription(SwitchEntityDescription):
    """Describes ThinQ switch entity."""

    on_key: str | None = None
    off_key: str | None = None


DEVICE_TYPE_SWITCH_MAP: dict[DeviceType, tuple[ThinQSwitchEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.AIR_CON_OPERATION_MODE,
            translation_key="operation_power",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.DISPLAY_LIGHT,
            translation_key=ThinQProperty.DISPLAY_LIGHT,
            on_key="on",
            off_key="off",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.POWER_SAVE_ENABLED,
            translation_key=ThinQProperty.POWER_SAVE_ENABLED,
            on_key="true",
            off_key="false",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.AIR_FAN_OPERATION_MODE, translation_key="operation_power"
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.UV_NANO,
            translation_key=ThinQProperty.UV_NANO,
            on_key="on",
            off_key="off",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.WARM_MODE,
            translation_key=ThinQProperty.WARM_MODE,
            on_key="warm_on",
            off_key="warm_off",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceType.AIR_PURIFIER: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
    ),
    DeviceType.DEHUMIDIFIER: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
    ),
    DeviceType.HUMIDIFIER: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
            translation_key="operation_power",
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.WARM_MODE,
            translation_key="humidity_warm_mode",
            on_key="warm_on",
            off_key="warm_off",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.MOOD_LAMP_STATE,
            translation_key=ThinQProperty.MOOD_LAMP_STATE,
            on_key="on",
            off_key="off",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.AUTO_MODE,
            translation_key=ThinQProperty.AUTO_MODE,
            on_key="auto_on",
            off_key="auto_off",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.SLEEP_MODE,
            translation_key=ThinQProperty.SLEEP_MODE,
            on_key="sleep_on",
            off_key="sleep_off",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceType.REFRIGERATOR: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.EXPRESS_MODE,
            translation_key=ThinQProperty.EXPRESS_MODE,
            on_key="true",
            off_key="false",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.RAPID_FREEZE,
            translation_key=ThinQProperty.RAPID_FREEZE,
            on_key="true",
            off_key="false",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.EXPRESS_FRIDGE,
            translation_key=ThinQProperty.EXPRESS_FRIDGE,
            on_key="true",
            off_key="false",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceType.SYSTEM_BOILER: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.BOILER_OPERATION_MODE,
            translation_key="operation_power",
            entity_category=EntityCategory.CONFIG,
        ),
        ThinQSwitchEntityDescription(
            key=ThinQProperty.HOT_WATER_MODE,
            translation_key=ThinQProperty.HOT_WATER_MODE,
            on_key="on",
            off_key="off",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceType.WINE_CELLAR: (
        ThinQSwitchEntityDescription(
            key=ThinQProperty.OPTIMAL_HUMIDITY,
            translation_key=ThinQProperty.OPTIMAL_HUMIDITY,
            on_key="on",
            off_key="off",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for switch platform."""
    entities: list[ThinQSwitchEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_SWITCH_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQSwitchEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_WRITE
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQSwitchEntity(ThinQEntity, SwitchEntity):
    """Represent a thinq switch platform."""

    entity_description: ThinQSwitchEntityDescription
    _attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        if (key := self.entity_description.on_key) is not None:
            self._attr_is_on = self.data.value == key
        else:
            self._attr_is_on = self.data.is_on

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.is_on,
            self.is_on,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug(
            "[%s:%s] async_turn_on id: %s",
            self.coordinator.device_name,
            self.name,
            self.property_id,
        )
        if (on_command := self.entity_description.on_key) is not None:
            await self.async_call_api(
                self.coordinator.api.post(self.property_id, on_command)
            )
        else:
            await self.async_call_api(
                self.coordinator.api.async_turn_on(self.property_id)
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off id: %s",
            self.coordinator.device_name,
            self.name,
            self.property_id,
        )
        if (off_command := self.entity_description.off_key) is not None:
            await self.async_call_api(
                self.coordinator.api.post(self.property_id, off_command)
            )
        else:
            await self.async_call_api(
                self.coordinator.api.async_turn_off(self.property_id)
            )
