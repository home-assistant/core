"""Matter ModeSelect Cluster Support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor, ClusterCommand
from chip.clusters.Types import Nullable
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
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


@dataclass(frozen=True)
class MatterSelectEntityDescription(SelectEntityDescription, MatterEntityDescription):
    """Describe Matter select entities."""


@dataclass(frozen=True, kw_only=True)
class MatterListSelectEntityDescription(MatterSelectEntityDescription):
    """Describe Matter select entities for MatterListSelectEntity."""

    # command: a callback to create the command to send to the device
    # the callback's argument will be the index of the selected list value
    command: Callable[[int], ClusterCommand]
    # list attribute: the attribute descriptor to get the list of values (= list of strings)
    list_attribute: type[ClusterAttributeDescriptor]


class MatterAttributeSelectEntity(MatterEntity, SelectEntity):
    """Representation of a select entity from Matter Attribute read/write."""

    entity_description: MatterSelectEntityDescription

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        value_convert = self.entity_description.ha_to_native_value
        if TYPE_CHECKING:
            assert value_convert is not None
        await self.matter_client.write_attribute(
            node_id=self._endpoint.node.node_id,
            attribute_path=create_attribute_path_from_attribute(
                self._endpoint.endpoint_id, self._entity_info.primary_attribute
            ),
            value=value_convert(option),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value: Nullable | int | None
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        value_convert = self.entity_description.measurement_to_ha
        if TYPE_CHECKING:
            assert value_convert is not None
        self._attr_current_option = value_convert(value)


class MatterModeSelectEntity(MatterAttributeSelectEntity):
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
        self._attr_current_option = modes.get(cluster.currentMode)
        # handle optional Description attribute as descriptive name for the mode
        if desc := getattr(cluster, "description", None):
            self._attr_name = desc


class MatterListSelectEntity(MatterEntity, SelectEntity):
    """Representation of a select entity from Matter list and selected item Cluster attribute(s)."""

    entity_description: MatterListSelectEntityDescription

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        option_id = self._attr_options.index(option)
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=self.entity_description.command(option_id),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        list_values = cast(
            list[str],
            self.get_matter_attribute_value(self.entity_description.list_attribute),
        )
        self._attr_options = list_values
        current_option_idx: int = self.get_matter_attribute_value(
            self._entity_info.primary_attribute
        )
        try:
            self._attr_current_option = list_values[current_option_idx]
        except IndexError:
            self._attr_current_option = None


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
            key="MatterRvcCleanMode",
            translation_key="clean_mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.RvcCleanMode.Attributes.CurrentMode,
            clusters.RvcCleanMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
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
        entity_description=MatterSelectEntityDescription(
            key="MatterDeviceEnergyManagementMode",
            translation_key="mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.DeviceEnergyManagementMode.Attributes.CurrentMode,
            clusters.DeviceEnergyManagementMode.Attributes.SupportedModes,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
            key="MatterStartUpOnOff",
            entity_category=EntityCategory.CONFIG,
            translation_key="startup_on_off",
            options=["on", "off", "toggle", "previous"],
            measurement_to_ha={
                0: "off",
                1: "on",
                2: "toggle",
                None: "previous",
            }.get,
            ha_to_native_value={
                "off": 0,
                "on": 1,
                "toggle": 2,
                "previous": None,
            }.get,
        ),
        entity_class=MatterAttributeSelectEntity,
        required_attributes=(clusters.OnOff.Attributes.StartUpOnOff,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
            key="SmokeCOSmokeSensitivityLevel",
            entity_category=EntityCategory.CONFIG,
            translation_key="sensitivity_level",
            options=["high", "standard", "low"],
            measurement_to_ha={
                0: "high",
                1: "standard",
                2: "low",
            }.get,
            ha_to_native_value={
                "high": 0,
                "standard": 1,
                "low": 2,
            }.get,
        ),
        entity_class=MatterAttributeSelectEntity,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.SmokeSensitivityLevel,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
            key="TrvTemperatureDisplayMode",
            entity_category=EntityCategory.CONFIG,
            translation_key="temperature_display_mode",
            options=["Celsius", "Fahrenheit"],
            measurement_to_ha={
                0: "Celsius",
                1: "Fahrenheit",
            }.get,
            ha_to_native_value={
                "Celsius": 0,
                "Fahrenheit": 1,
            }.get,
        ),
        entity_class=MatterAttributeSelectEntity,
        required_attributes=(
            clusters.ThermostatUserInterfaceConfiguration.Attributes.TemperatureDisplayMode,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterListSelectEntityDescription(
            key="TemperatureControlSelectedTemperatureLevel",
            translation_key="temperature_level",
            command=lambda selected_index: clusters.TemperatureControl.Commands.SetTemperature(
                targetTemperatureLevel=selected_index
            ),
            list_attribute=clusters.TemperatureControl.Attributes.SupportedTemperatureLevels,
        ),
        entity_class=MatterListSelectEntity,
        required_attributes=(
            clusters.TemperatureControl.Attributes.SelectedTemperatureLevel,
            clusters.TemperatureControl.Attributes.SupportedTemperatureLevels,
        ),
    ),
]
