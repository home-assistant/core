"""Matter Number Inputs."""

from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, Platform, UnitOfTime
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
    """Set up Matter Number Input from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.NUMBER, async_add_entities)


@dataclass(frozen=True)
class MatterNumberEntityDescription(NumberEntityDescription, MatterEntityDescription):
    """Describe Matter Number Input entities."""


class MatterNumber(MatterEntity, NumberEntity):
    """Representation of a Matter Attribute as a Number entity."""

    entity_description: MatterNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        matter_attribute = self._entity_info.primary_attribute
        sendvalue = int(value)
        if value_convert := self.entity_description.ha_to_native_measurement:
            sendvalue = value_convert(value)
        await self.matter_client.write_attribute(
            node_id=self._endpoint.node.node_id,
            attribute_path=create_attribute_path_from_attribute(
                self._endpoint.endpoint_id,
                matter_attribute,
            ),
            value=sendvalue,
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value in (None, NullValue):
            value = None
        elif value_convert := self.entity_description.measurement_to_ha:
            value = value_convert(value)
        self._attr_native_value = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_level",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_level",
            native_max_value=100,
            native_min_value=1,
            mode=NumberMode.BOX,
            measurement_to_ha=lambda x: round(x / 2.54),
            ha_to_native_measurement=lambda x: round(x * 2.54),
            native_step=1,
            native_unit_of_measurement=PERCENTAGE,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnLevel,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_transition_time",
            native_max_value=65534,
            native_min_value=0,
            measurement_to_ha=lambda x: x / 10,
            ha_to_native_measurement=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnTransitionTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="off_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="off_transition_time",
            native_max_value=65534,
            native_min_value=0,
            measurement_to_ha=lambda x: x / 10,
            ha_to_native_measurement=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OffTransitionTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_off_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_off_transition_time",
            native_max_value=65534,
            native_min_value=0,
            measurement_to_ha=lambda x: x / 10,
            ha_to_native_measurement=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnOffTransitionTime,),
    ),
]
