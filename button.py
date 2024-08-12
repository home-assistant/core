"""Matter Button Inputs for Identify function."""

from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as clusters

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Button"""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BUTTON, async_add_entities)


@dataclass(frozen=True)
class MatterButtonEntityDescription(ButtonEntityDescription, MatterEntityDescription):
    """Describe Matter Button entities."""


class MatterIdentifyButton(MatterEntity, ButtonEntity):
    """Representation of a Matter Identify Command as a Button entity."""

    entity_description: MatterButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the Idnetify button press"""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=clusters.Identify.Commands.Identify(identifyTime=15),
        )
    @callback
    def _update_from_device(self) -> None:
        """Update from device."""


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="identify",
            entity_category=EntityCategory.CONFIG,
            device_class=ButtonDeviceClass.IDENTIFY,
        ),
        entity_class=MatterIdentifyButton,
        required_attributes=(clusters.Identify.Attributes.IdentifyTime,),
    ),
]
