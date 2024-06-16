"""Matter ModeSelect Cluster Support."""

from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform, 
    EntityCategory 
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter ModeSelect from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SELECT, async_add_entities)


class MatterModeSelect(MatterEntity, SelectEntity):
    """Representation of a Matter select."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        self._attr_name = self.get_matter_attribute_value( clusters.ModeSelect.Attributes.Description )
        

    async def async_select_option(self, option: str) -> None:
        """Change the device mode"""
        supportedmodes = self.get_matter_attribute_value(
            clusters.ModeSelect.Attributes.SupportedModes
        )
        for mode in supportedmodes:
            if option == mode.label:  newselectmode = mode.mode
            
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=clusters.ModeSelect.Commands.ChangeToMode(newMode=newselectmode),
        )
        
    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        currentmode = self.get_matter_attribute_value(
            clusters.ModeSelect.Attributes.CurrentMode
        )
        
    @property
    def options(self)->list[str]:
        supportedmodes = self.get_matter_attribute_value(
            clusters.ModeSelect.Attributes.SupportedModes
        )
        supportedmodelist = []
        for option in supportedmodes:
            supportedmodelist.append(option.label)
        return supportedmodelist

    @property
    def current_option(self) -> str:
        currentmode = self.get_matter_attribute_value(
            clusters.ModeSelect.Attributes.CurrentMode
        )
        supportedmodes = self.get_matter_attribute_value(
            clusters.ModeSelect.Attributes.SupportedModes
        )
        for mode in supportedmodes:
            if currentmode == mode.mode:  return(mode.label)


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterModeSelect", 
            entity_category=EntityCategory.CONFIG,
            name=None
        ),
        entity_class=MatterModeSelect,
        required_attributes=(
            clusters.ModeSelect.Attributes.Description,
            clusters.ModeSelect.Attributes.StandardNamespace,
            clusters.ModeSelect.Attributes.SupportedModes,
            clusters.ModeSelect.Attributes.CurrentMode,
        ),
    ),
]
