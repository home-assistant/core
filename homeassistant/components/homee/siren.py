"""The homee siren platform."""

from typing import Any

from pyHomee.const import AttributeType

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add siren entities for homee."""

    async_add_devices(
        HomeeSiren(attribute, config_entry)
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type == AttributeType.SIREN
    )


class HomeeSiren(HomeeEntity, SirenEntity):
    """Representation of a homee siren device."""

    _attr_name = None
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    @property
    def is_on(self) -> bool:
        """Return the state of the siren."""
        return self._attribute.current_value == 1.0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        await self.async_set_homee_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self.async_set_homee_value(0)
