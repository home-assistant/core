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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .const import CLIMATE_PROFILES, LIGHT_PROFILES
from .entity import HomeeEntity

PARALLEL_UPDATES = 0


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
    AttributeType.EXTERNAL_BINARY_INPUT: HomeeSwitchEntityDescription(
        key="external_binary_input", entity_category=EntityCategory.CONFIG
    ),
    AttributeType.MANUAL_OPERATION: HomeeSwitchEntityDescription(
        key="manual_operation"
    ),
    AttributeType.ON_OFF: HomeeSwitchEntityDescription(
        key="on_off", device_class_fn=get_device_class, name=None
    ),
    AttributeType.WATCHDOG_ON_OFF: HomeeSwitchEntityDescription(
        key="watchdog", entity_category=EntityCategory.CONFIG
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform for the Homee component."""

    for node in config_entry.runtime_data.nodes:
        async_add_devices(
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


class HomeeSwitch(HomeeEntity, SwitchEntity):
    """Representation of a Homee switch."""

    entity_description: HomeeSwitchEntityDescription

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeSwitchEntityDescription,
    ) -> None:
        """Initialize a Homee switch entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        if attribute.instance == 0:
            if attribute.type == AttributeType.ON_OFF:
                self._attr_name = None
            else:
                self._attr_translation_key = description.key
        else:
            self._attr_translation_key = f"{description.key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return bool(self._attribute.current_value)

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return the device class of the switch."""
        return self.entity_description.device_class_fn(self._attribute, self._entry)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.async_set_homee_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.async_set_homee_value(0)
