"""Matter ModeSelect Cluster Support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor, ClusterCommand
from chip.clusters.Types import Nullable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema

NUMBER_OF_RINSES_STATE_MAP = {
    clusters.LaundryWasherControls.Enums.NumberOfRinsesEnum.kNone: "off",
    clusters.LaundryWasherControls.Enums.NumberOfRinsesEnum.kNormal: "normal",
    clusters.LaundryWasherControls.Enums.NumberOfRinsesEnum.kExtra: "extra",
    clusters.LaundryWasherControls.Enums.NumberOfRinsesEnum.kMax: "max",
    clusters.LaundryWasherControls.Enums.NumberOfRinsesEnum.kUnknownEnumValue: None,
}
NUMBER_OF_RINSES_STATE_MAP_REVERSE = {
    v: k for k, v in NUMBER_OF_RINSES_STATE_MAP.items()
}

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
    | clusters.WaterHeaterMode
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter ModeSelect from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SELECT, async_add_entities)


@dataclass(frozen=True)
class MatterSelectEntityDescription(SelectEntityDescription, MatterEntityDescription):
    """Describe Matter select entities."""


@dataclass(frozen=True, kw_only=True)
class MatterMapSelectEntityDescription(MatterSelectEntityDescription):
    """Describe Matter select entities for MatterMapSelectEntityDescription."""

    measurement_to_ha: Callable[[int], str | None]
    ha_to_native_value: Callable[[str], int | None]

    # list attribute: the attribute descriptor to get the list of values (= list of integers)
    list_attribute: type[ClusterAttributeDescriptor]


@dataclass(frozen=True, kw_only=True)
class MatterListSelectEntityDescription(MatterSelectEntityDescription):
    """Describe Matter select entities for MatterListSelectEntity."""

    # list attribute: the attribute descriptor to get the list of values (= list of strings)
    list_attribute: type[ClusterAttributeDescriptor]
    # command: a custom callback to create the command to send to the device
    # the callback's argument will be the index of the selected list value
    # if omitted the command will just be a write_attribute command to the primary attribute
    command: Callable[[int], ClusterCommand] | None = None


class MatterAttributeSelectEntity(MatterEntity, SelectEntity):
    """Representation of a select entity from Matter Attribute read/write."""

    entity_description: MatterSelectEntityDescription

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        value_convert = self.entity_description.ha_to_native_value
        if TYPE_CHECKING:
            assert value_convert is not None
        await self.write_attribute(
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


class MatterMapSelectEntity(MatterAttributeSelectEntity):
    """Representation of a Matter select entity where the options are defined in a State map."""

    entity_description: MatterMapSelectEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # the options can dynamically change based on the state of the device
        available_values = cast(
            list[int],
            self.get_matter_attribute_value(self.entity_description.list_attribute),
        )
        # map available (int) values to string representation
        self._attr_options = [
            mapped_value
            for value in available_values
            if (mapped_value := self.entity_description.measurement_to_ha(value))
        ]
        # use base implementation from MatterAttributeSelectEntity to set the current option
        super()._update_from_device()


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
            await self.send_device_command(
                cluster.Commands.ChangeToMode(newMode=mode.mode),
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

        if TYPE_CHECKING:
            assert option_id is not None

        if self.entity_description.command:
            # custom command defined to set the new value
            await self.send_device_command(
                self.entity_description.command(option_id),
            )
            return
        # regular write attribute to set the new value
        await self.write_attribute(
            value=option_id,
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterSelectEntityDescription(
            key="MatterDeviceEnergyManagementMode",
            translation_key="device_energy_management_mode",
        ),
        entity_class=MatterModeSelectEntity,
        required_attributes=(
            clusters.DeviceEnergyManagementMode.Attributes.CurrentMode,
            clusters.DeviceEnergyManagementMode.Attributes.SupportedModes,
        ),
        # don't discover this entry if the supported modes list is empty
        secondary_value_is_not=[],
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
        # allow None value for previous state
        allow_none_value=True,
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
        # don't discover this entry if the supported levels list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterListSelectEntityDescription(
            key="LaundryWasherControlsSpinSpeed",
            translation_key="laundry_washer_spin_speed",
            list_attribute=clusters.LaundryWasherControls.Attributes.SpinSpeeds,
        ),
        entity_class=MatterListSelectEntity,
        required_attributes=(
            clusters.LaundryWasherControls.Attributes.SpinSpeedCurrent,
            clusters.LaundryWasherControls.Attributes.SpinSpeeds,
        ),
        # don't discover this entry if the spinspeeds list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SELECT,
        entity_description=MatterMapSelectEntityDescription(
            key="MatterLaundryWasherNumberOfRinses",
            translation_key="laundry_washer_number_of_rinses",
            list_attribute=clusters.LaundryWasherControls.Attributes.SupportedRinses,
            measurement_to_ha=NUMBER_OF_RINSES_STATE_MAP.get,
            ha_to_native_value=NUMBER_OF_RINSES_STATE_MAP_REVERSE.get,
        ),
        entity_class=MatterMapSelectEntity,
        required_attributes=(
            clusters.LaundryWasherControls.Attributes.NumberOfRinses,
            clusters.LaundryWasherControls.Attributes.SupportedRinses,
        ),
        # don't discover this entry if the supported rinses list is empty
        secondary_value_is_not=[],
    ),
]
