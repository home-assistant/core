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

type SelectCluster = (
    clusters.ModeSelect
    | clusters.OvenMode
    | clusters.LaundryWasherMode
    | clusters.RefrigeratorAndTemperatureControlledCabinetMode
    | clusters.RvcRunMode
    | clusters.RvcCleanMode
    | clusters.DishwasherMode
    | clusters.MicrowaveOvenMode
    | clusters.EnergyEvseMode
    | clusters.DeviceEnergyManagementMode
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter ModeSelect from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SELECT, async_add_entities)


class MatterModeSelectEntity(MatterEntity, SelectEntity):
    """Representation of a select entity from Matter (Mode) Cluster attribute(s)."""

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        cluster: SelectCluster = self._endpoint.get_cluster(
            self._entity_info.primary_attribute.cluster_id
        )
        # select the mode ID from the label string
        for mode in cluster.supportedModes:
            if mode.label != option:
                continue
            await self.matter_client.send_device_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command=cluster.Commands.ChangeToMode(newMode=mode.mode),
            )
            break

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # NOTE: cluster can be ModeSelect or a variant of that,
        # such as DishwasherMode. They all have the same characteristics.
        cluster: SelectCluster = self._endpoint.get_cluster(
            self._entity_info.primary_attribute.cluster_id
        )
        modes = {mode.mode: mode.label for mode in cluster.supportedModes}
        self._attr_options = list(modes.values())
        self._attr_current_option = modes[cluster.currentMode]
        # handle optional Description attribute as descriptive name for the mode
        if desc := getattr(cluster, "description", None):
            self._attr_name = desc


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterModeSelect",
            entity_category=EntityCategory.CONFIG,
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.ModeSelect.Attributes.CurrentMode,
            clusters.ModeSelect.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterOvenMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.OvenMode.Attributes.CurrentMode,
            clusters.OvenMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterLaundryWasherMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.LaundryWasherMode.Attributes.CurrentMode,
            clusters.LaundryWasherMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterRefrigeratorAndTemperatureControlledCabinetMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.RefrigeratorAndTemperatureControlledCabinetMode.Attributes.CurrentMode,
            clusters.RefrigeratorAndTemperatureControlledCabinetMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterRvcRunMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.RvcRunMode.Attributes.CurrentMode,
            clusters.RvcRunMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterRvcCleanMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.RvcCleanMode.Attributes.CurrentMode,
            clusters.RvcCleanMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterDishwasherMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.DishwasherMode.Attributes.CurrentMode,
            clusters.DishwasherMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterMicrowaveOvenMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.MicrowaveOvenMode.Attributes.CurrentMode,
            clusters.MicrowaveOvenMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterEnergyEvseMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.EnergyEvseMode.Attributes.CurrentMode,
            clusters.EnergyEvseMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=SelectEntityDescription(
            key="MatterDeviceEnergyManagementMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.DeviceEnergyManagementMode.Attributes.CurrentMode,
            clusters.DeviceEnergyManagementMode.Attributes.SupportedModes,
        ),
    ),
]
