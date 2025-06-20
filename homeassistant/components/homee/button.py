"""The homee button platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0

BUTTON_DESCRIPTIONS: dict[AttributeType, ButtonEntityDescription] = {
    AttributeType.AUTOMATIC_MODE_IMPULSE: ButtonEntityDescription(key="automatic_mode"),
    AttributeType.BRIEFLY_OPEN_IMPULSE: ButtonEntityDescription(key="briefly_open"),
    AttributeType.IDENTIFICATION_MODE: ButtonEntityDescription(
        key="identification_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=ButtonDeviceClass.IDENTIFY,
    ),
    AttributeType.IMPULSE: ButtonEntityDescription(key="impulse"),
    AttributeType.LIGHT_IMPULSE: ButtonEntityDescription(key="light"),
    AttributeType.OPEN_PARTIAL_IMPULSE: ButtonEntityDescription(key="open_partial"),
    AttributeType.PERMANENTLY_OPEN_IMPULSE: ButtonEntityDescription(
        key="permanently_open"
    ),
    AttributeType.RESET_METER: ButtonEntityDescription(
        key="reset_meter",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.VENTILATE_IMPULSE: ButtonEntityDescription(key="ventilate"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the button component."""

    async_add_entities(
        HomeeButton(attribute, config_entry, BUTTON_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in BUTTON_DESCRIPTIONS and attribute.editable
    )


class HomeeButton(HomeeEntity, ButtonEntity):
    """Representation of a Homee button."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize a Homee button entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        if attribute.instance == 0:
            if attribute.type == AttributeType.IMPULSE:
                self._attr_name = None
            else:
                self._attr_translation_key = description.key
        else:
            self._attr_translation_key = f"{description.key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.async_set_homee_value(1)
