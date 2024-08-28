"""Support for switch entities."""

from __future__ import annotations

from collections.abc import Collection
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
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .const import POWER_OFF, POWER_ON, THINQ_DEVICE_ADDED
from .coordinator import DeviceDataUpdateCoordinator
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
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.AIR_FAN_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.AIR_PURIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.AIR_PURIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.BOILER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.BOILER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.BOILER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.DEHUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
    ThinQProperty.HUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
            value_converter=value_to_power_state_converter,
        ),
    ),
}

AIR_PURIFIER_FAN_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[ThinQProperty.AIR_FAN_OPERATION_MODE],
)
AIRPURIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[ThinQProperty.AIR_PURIFIER_OPERATION_MODE],
)
DEHUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[ThinQProperty.DEHUMIDIFIER_OPERATION_MODE],
)
HUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[ThinQProperty.HUMIDIFIER_OPERATION_MODE],
)
SYSTEM_BOILER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[ThinQProperty.BOILER_OPERATION_MODE],
)

DEVIE_TYPE_SWITCH_MAP = {
    DeviceType.AIR_PURIFIER_FAN: AIR_PURIFIER_FAN_SWITCH,
    DeviceType.AIR_PURIFIER: AIRPURIFIER_SWITCH,
    DeviceType.DEHUMIDIFIER: DEHUMIDIFIER_SWITCH,
    DeviceType.HUMIDIFIER: HUMIDIFIER_SWITCH,
    DeviceType.SYSTEM_BOILER: SYSTEM_BOILER_SWITCH,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for switch platform."""

    @callback
    def add_entities(
        coordinators: Collection[DeviceDataUpdateCoordinator],
    ) -> None:
        """Add switch entities."""
        for coordinator in coordinators:
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

                entities += [
                    ThinQSwitchEntity(coordinator, description, prop)
                    for prop in properties
                ]

            if entities:
                for entity in entities:
                    _LOGGER.debug(
                        "[%s] Add %s:%s entity",
                        coordinator.device_name,
                        Platform.SWITCH,
                        entity.entity_description.key,
                    )
                async_add_entities(entities)

    add_entities(entry.runtime_data.values())

    entry.async_on_unload(
        async_dispatcher_connect(hass, THINQ_DEVICE_ADDED, add_entities)
    )


class ThinQSwitchEntity(ThinQEntity, SwitchEntity):
    """Represent a thinq switch platform."""

    entity_description: ThinQSwitchEntityDescription
    attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_is_on = self.get_value_as_bool()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._attr_is_on = True
        self.async_write_ha_state()

        _LOGGER.debug("[%s] async_turn_on", self.name)
        await self.async_post_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._attr_is_on = False
        self.async_write_ha_state()

        _LOGGER.debug("[%s] async_turn_off", self.name)
        await self.async_post_value(False)
