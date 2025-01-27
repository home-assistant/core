"""The homee switch platform."""

from dataclasses import dataclass
import logging
from typing import Any

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeeConfigEntry
from .const import CLIMATE_PROFILES, LIGHT_PROFILES
from .entity import HomeeEntity

_LOGGER = logging.getLogger(__name__)

DESCRIPTIVE_ATTRIBUTES = [
    AttributeType.AUTOMATIC_MODE_IMPULSE,
    AttributeType.BRIEFLY_OPEN_IMPULSE,
    AttributeType.EXTERNAL_BINARY_INPUT,
    AttributeType.IDENTIFICATION_MODE,
    AttributeType.LIGHT_IMPULSE,
    AttributeType.MANUAL_OPERATION,
    AttributeType.MOTOR_ROTATION,
    AttributeType.OPEN_PARTIAL_IMPULSE,
    AttributeType.PERMANENTLY_OPEN_IMPULSE,
    AttributeType.RESET_METER,
    AttributeType.RESTORE_LAST_KNOWN_STATE,
    AttributeType.SWITCH_TYPE,
    AttributeType.VENTILATE_IMPULSE,
    AttributeType.WATCHDOG_ON_OFF,
]


@dataclass(frozen=True, kw_only=True)
class HomeeSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes Homee switch entity."""

    device_class: SwitchDeviceClass = SwitchDeviceClass.SWITCH


SWITCH_DESCRIPTIONS: dict[AttributeType, HomeeSwitchEntityDescription] = {
    AttributeType.AUTOMATIC_MODE_IMPULSE: HomeeSwitchEntityDescription(
        key="automatic_mode_impulse"
    ),
    AttributeType.BRIEFLY_OPEN_IMPULSE: HomeeSwitchEntityDescription(
        key="briefly_open_impulse"
    ),
    AttributeType.EXTERNAL_BINARY_INPUT: HomeeSwitchEntityDescription(
        key="external_binary_input", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.IDENTIFICATION_MODE: HomeeSwitchEntityDescription(
        key="identification_mode", entity_category=EntityCategory.DIAGNOSTIC
    ),
    AttributeType.IMPULSE: HomeeSwitchEntityDescription(key="impulse"),
    AttributeType.LIGHT_IMPULSE: HomeeSwitchEntityDescription(key="light_impulse"),
    AttributeType.MANUAL_OPERATION: HomeeSwitchEntityDescription(
        key="manual_operation"
    ),
    AttributeType.MOTOR_ROTATION: HomeeSwitchEntityDescription(
        key="motor_rotation", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.OPEN_PARTIAL_IMPULSE: HomeeSwitchEntityDescription(
        key="open_partial_impulse"
    ),
    AttributeType.ON_OFF: HomeeSwitchEntityDescription(key="on_off"),
    AttributeType.PERMANENTLY_OPEN_IMPULSE: HomeeSwitchEntityDescription(
        key="permanently_open_impulse"
    ),
    AttributeType.RESET_METER: HomeeSwitchEntityDescription(
        key="reset_meter", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.RESTORE_LAST_KNOWN_STATE: HomeeSwitchEntityDescription(
        key="restore_last_known_state", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.SWITCH_TYPE: HomeeSwitchEntityDescription(
        key="switch_type", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.VENTILATE_IMPULSE: HomeeSwitchEntityDescription(
        key="ventilate_impulse"
    ),
    AttributeType.WATCHDOG_ON_OFF: HomeeSwitchEntityDescription(
        key="watchdog_on_off", entity_category=EntityCategory.CONFIG
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Add the homee platform for the switch component."""

    devices: list[HomeeSwitch] = []
    for node in config_entry.runtime_data.nodes:
        devices.extend(
            HomeeSwitch(attribute, config_entry, SWITCH_DESCRIPTIONS[attribute.type])
            for attribute in node.attributes
            if (attribute.type in SWITCH_DESCRIPTIONS and attribute.editable)
            and not (
                attribute.type == AttributeType.ON_OFF
                and node.profile in LIGHT_PROFILES
            )
            and not (
                attribute.type == AttributeType.MANUAL_OPERATION
                and node.profile in CLIMATE_PROFILES
            )
        )
    if devices:
        async_add_devices(devices)


class HomeeSwitch(HomeeEntity, SwitchEntity):
    """Representation of a homee switch."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeSwitchEntityDescription,
    ) -> None:
        """Initialize a homee switch entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_is_on = bool(attribute.current_value)
        self._attr_translation_key = description.key
        if attribute.instance > 0:
            self._attr_translation_key = f"{self._attr_translation_key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    @property
    def icon(self) -> str | None:
        """Return icon if different from main feature."""
        if self._attribute.type == AttributeType.WATCHDOG_ON_OFF:
            return "mdi:dog"
        if self._attribute.type == AttributeType.MANUAL_OPERATION:
            return "mdi:hand-back-left"

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.async_set_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_set_value(0)
