"""Matter sirens."""

from dataclasses import dataclass
from typing import Any

from matter_server.common.custom_clusters import HeimanCluster

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter sirens from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.SIREN, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterSirenEntityDescription(SirenEntityDescription, MatterEntityDescription):
    """Describe Matter Siren entities."""


class MatterSiren(MatterEntity, SirenEntity):
    """Representation of a Matter siren."""

    entity_description: MatterSirenEntityDescription
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        await self.write_attribute(value=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self.write_attribute(value=0)

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        self._attr_is_on = bool(value) if value is not None else None


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SIREN,
        entity_description=MatterSirenEntityDescription(
            key="HeimanSiren",
            translation_key="siren",
        ),
        entity_class=MatterSiren,
        required_attributes=(HeimanCluster.Attributes.SirenActive,),
    ),
]
