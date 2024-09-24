"""Matter Button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Button platform."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BUTTON, async_add_entities)


@dataclass(frozen=True)
class MatterButtonEntityDescription(ButtonEntityDescription, MatterEntityDescription):
    """Describe Matter Button entities."""

    command: Callable[[], Any]


class MatterCommandButton(MatterEntity, ButtonEntity):
    """Representation of a Matter Button entity."""

    entity_description: MatterButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press leveraging a Matter command."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=self.entity_description.command(),
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="IdentifyButton",
            entity_category=EntityCategory.CONFIG,
            device_class=ButtonDeviceClass.IDENTIFY,
            command=lambda: clusters.Identify.Commands.Identify(identifyTime=15),
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.Identify.Attributes.IdentifyTime,),
    ),
]
