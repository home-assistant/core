"""The Homee select platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

SELECT_DESCRIPTIONS: dict[AttributeType, SelectEntityDescription] = {
    AttributeType.MOTOR_ROTATION: SelectEntityDescription(
        key="motor_rotation",
        options=["normal", "reverse"],
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.REPEATER_MODE: SelectEntityDescription(
        key="repeater_mode",
        options=["off", "level1", "level2"],
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.RESTORE_LAST_KNOWN_STATE: SelectEntityDescription(
        key="restore_last_known_state",
        options=["disabled", "enabled"],
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SWITCH_TYPE: SelectEntityDescription(
        key="switch_type",
        options=["0", "1", "2"],
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.WIND_MONITORING_STATE: SelectEntityDescription(
        key="wind_monitoring_state",
        options=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the select integration."""

    async_add_entities(
        HomeeSelect(attribute, config_entry, SELECT_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in SELECT_DESCRIPTIONS and attribute.editable
    )


class HomeeSelect(HomeeEntity, SelectEntity):
    """Representation of a Homee select device."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize a Homee select entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        assert description.options is not None
        self._attr_options = description.options
        self._attr_translation_key = description.key

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return self.options[int(self._attribute.current_value)]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.async_set_homee_value(self.options.index(option))
