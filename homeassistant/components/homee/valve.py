"""The Homee valve platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0

VALVE_DESCRIPTIONS = {
    AttributeType.CURRENT_VALVE_POSITION: ValveEntityDescription(
        key="valve_position",
        device_class=ValveDeviceClass.WATER,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the valve component."""

    async_add_entities(
        HomeeValve(attribute, config_entry, VALVE_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in VALVE_DESCRIPTIONS
    )


class HomeeValve(HomeeEntity, ValveEntity):
    """Representation of a Homee valve."""

    _attr_reports_position = True

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: ValveEntityDescription,
    ) -> None:
        """Initialize a Homee valve entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def supported_features(self) -> ValveEntityFeature:
        """Return the supported features."""
        if self._attribute.editable:
            return ValveEntityFeature.SET_POSITION
        return ValveEntityFeature(0)

    @property
    def current_valve_position(self) -> int | None:
        """Return the current valve position."""
        return int(self._attribute.current_value)

    @property
    def is_closing(self) -> bool:
        """Return if the valve is closing."""
        return self._attribute.target_value < self._attribute.current_value

    @property
    def is_opening(self) -> bool:
        """Return if the valve is opening."""
        return self._attribute.target_value > self._attribute.current_value

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self.async_set_homee_value(position)
