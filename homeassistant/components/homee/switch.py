"""The homee switch platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyHomee.const import AttributeType, NodeProfile
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


def get_device_class(
    attribute: HomeeAttribute, config_entry: HomeeConfigEntry
) -> SwitchDeviceClass:
    """Check device class of Switch according to node profile."""
    node = config_entry.runtime_data.get_node_by_id(attribute.node_id)
    if node.profile in [
        NodeProfile.ON_OFF_PLUG,
        NodeProfile.METERING_PLUG,
        NodeProfile.DOUBLE_ON_OFF_PLUG,
        NodeProfile.IMPULSE_PLUG,
    ]:
        return SwitchDeviceClass.OUTLET

    return SwitchDeviceClass.SWITCH


@dataclass(frozen=True, kw_only=True)
class HomeeSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes Homee switch entity."""

    device_class_fn: Callable[[HomeeAttribute, HomeeConfigEntry], SwitchDeviceClass] = (
        lambda attribute, entry: SwitchDeviceClass.SWITCH
    )


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
    AttributeType.ON_OFF: HomeeSwitchEntityDescription(
        key="on_off", device_class_fn=get_device_class
    ),
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

    entity_description: HomeeSwitchEntityDescription

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
    def device_class(self) -> SwitchDeviceClass:
        """Return the device class of the switch."""
        return self.entity_description.device_class_fn(self._attribute, self._entry)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.async_set_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.async_set_value(0)
