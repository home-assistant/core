"""Matter ModeSelect Cluster Support."""

from __future__ import annotations

from chip.clusters import Objects as clusters

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

SelectCluster = (
    clusters.ModeSelect | clusters.DishwasherMode | clusters.LaundryWasherMode
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter ModeSelect from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SELECT, async_add_entities)


class MatterSelectEntity(MatterEntity, SelectEntity):
    """Representation of a select entity from Matter cluster attribute(s)."""

    async def async_select_option(self, option: str) -> None:
        """Change the device mode."""

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        cluster: clusters.ModeSelect = self._endpoint.get_cluster(
            self._entity_info.primary_attribute.cluster_id
        )
        modes = {mode.mode: mode.label for mode in cluster.supportedModes}
        self._attr_options = list(modes.values())
        self._attr_current_option = modes[cluster.currentMode]


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterModeSelect",
            entity_category=EntityCategory.CONFIG,
            name="MatterModeSelect",
        ),
        entity_class=MatterSelectEntity,
        required_attributes=(
            clusters.ModeSelect.Attributes.SupportedModes,
            clusters.ModeSelect.Attributes.CurrentMode,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="DishwasherMode",
            name="Dishwasher Mode",
        ),
        entity_class=MatterSelectEntity,
        required_attributes=(
            clusters.DishwasherMode.Attributes.SupportedModes,
            clusters.DishwasherMode.Attributes.CurrentMode,
        ),
    ),
]
