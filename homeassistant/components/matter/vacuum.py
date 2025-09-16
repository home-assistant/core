"""Matter vacuum platform."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast

from chip.clusters import Objects as clusters
from chip.clusters.Objects import NullValue
from matter_server.client.models import device_types
import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SERVICE_CLEAN_AREAS, SERVICE_GET_AREAS, SERVICE_SELECT_AREAS
from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

ATTR_CURRENT_AREA = "current_area"
ATTR_CURRENT_AREA_NAME = "current_area_name"
ATTR_SELECTED_AREAS = "selected_areas"


class OperationalState(IntEnum):
    """Operational State of the vacuum cleaner.

    Combination of generic OperationalState and RvcOperationalState.
    """

    STOPPED = 0x00
    RUNNING = 0x01
    PAUSED = 0x02
    ERROR = 0x03
    SEEKING_CHARGER = 0x40
    CHARGING = 0x41
    DOCKED = 0x42


class ModeTag(IntEnum):
    """Enum with available ModeTag values."""

    IDLE = 0x4000  # 16384 decimal
    CLEANING = 0x4001  # 16385 decimal
    MAPPING = 0x4002  # 16386 decimal


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter vacuum platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.VACUUM, async_add_entities)
    platform = entity_platform.async_get_current_platform()

    # This will call Entity.async_handle_get_areas
    platform.async_register_entity_service(
        SERVICE_GET_AREAS,
        schema=None,
        func="async_handle_get_areas",
        supports_response=SupportsResponse.ONLY,
    )

    # This will call Entity.async_handle_clean_areas
    platform.async_register_entity_service(
        SERVICE_CLEAN_AREAS,
        schema={
            vol.Required("areas"): vol.All(cv.ensure_list, [cv.positive_int]),
        },
        func="async_handle_clean_areas",
        supports_response=SupportsResponse.ONLY,
    )
    # This will call Entity.async_handle_select_areas
    platform.async_register_entity_service(
        SERVICE_SELECT_AREAS,
        schema={
            vol.Required("areas"): vol.All(cv.ensure_list, [cv.positive_int]),
        },
        func="async_handle_select_areas",
        supports_response=SupportsResponse.ONLY,
    )


class MatterVacuum(MatterEntity, StateVacuumEntity):
    """Representation of a Matter Vacuum cleaner entity."""

    _last_accepted_commands: list[int] | None = None
    _supported_run_modes: (
        dict[int, clusters.RvcRunMode.Structs.ModeOptionStruct] | None
    ) = None
    _attr_matter_areas: dict[str, Any] | None = None
    _attr_current_area: int | None = None
    _attr_current_area_name: str | None = None
    _attr_selected_areas: list[int] | None = None
    _attr_supported_maps: list[dict[str, Any]] | None = None
    entity_description: StateVacuumEntityDescription
    _platform_translation_key = "vacuum"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {
            ATTR_CURRENT_AREA: self._attr_current_area,
            ATTR_CURRENT_AREA_NAME: self._attr_current_area_name,
            ATTR_SELECTED_AREAS: self._attr_selected_areas,
        }

    def _get_run_mode_by_tag(
        self, tag: ModeTag
    ) -> clusters.RvcRunMode.Structs.ModeOptionStruct | None:
        """Get the run mode by tag."""
        supported_run_modes = self._supported_run_modes or {}
        for mode in supported_run_modes.values():
            for t in mode.modeTags:
                if t.value == tag.value:
                    return mode
        return None

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        # We simply set the RvcRunMode to the first runmode
        # that has the idle tag to stop the vacuum cleaner.
        # this is compatible with both Matter 1.2 and 1.3+ devices.
        mode = self._get_run_mode_by_tag(ModeTag.IDLE)
        if mode is None:
            raise HomeAssistantError(
                "No supported run mode found to stop the vacuum cleaner."
            )

        await self.send_device_command(
            clusters.RvcRunMode.Commands.ChangeToMode(newMode=mode.mode)
        )

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.send_device_command(clusters.RvcOperationalState.Commands.GoHome())

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self.send_device_command(clusters.Identify.Commands.Identify())

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        if TYPE_CHECKING:
            assert self._last_accepted_commands is not None

        accepted_operational_commands = self._last_accepted_commands
        if (
            clusters.RvcOperationalState.Commands.Resume.command_id
            in accepted_operational_commands
            and self.state == VacuumActivity.PAUSED
        ):
            # vacuum is paused and supports resume command
            await self.send_device_command(
                clusters.RvcOperationalState.Commands.Resume()
            )
            return

        # We simply set the RvcRunMode to the first runmode
        # that has the cleaning tag to start the vacuum cleaner.
        # this is compatible with both Matter 1.2 and 1.3+ devices.
        mode = self._get_run_mode_by_tag(ModeTag.CLEANING)
        if mode is None:
            raise HomeAssistantError(
                "No supported run mode found to start the vacuum cleaner."
            )

        await self.send_device_command(
            clusters.RvcRunMode.Commands.ChangeToMode(newMode=mode.mode)
        )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_device_command(clusters.RvcOperationalState.Commands.Pause())

    def async_get_areas(self, **kwargs: Any) -> dict[str, Any]:
        """Get available area and map IDs from vacuum appliance."""

        supported_areas = self.get_matter_attribute_value(
            clusters.ServiceArea.Attributes.SupportedAreas
        )
        if not supported_areas:
            raise HomeAssistantError("Can't get areas from the device.")

        # Group by area_id: {area_id: {"map_id": ..., "name": ...}}
        areas = {}
        for area in supported_areas:
            area_id = getattr(area, "areaID", None)
            map_id = getattr(area, "mapID", None)
            location_name = None
            area_info = getattr(area, "areaInfo", None)
            if area_info is not None:
                location_info = getattr(area_info, "locationInfo", None)
                if location_info is not None:
                    location_name = getattr(location_info, "locationName", None)
            if area_id is not None:
                areas[area_id] = {"map_id": map_id, "name": location_name}

        # Optionally, also extract supported maps if available
        supported_maps = self.get_matter_attribute_value(
            clusters.ServiceArea.Attributes.SupportedMaps
        )
        maps = []
        if supported_maps:
            maps = [
                {
                    "map_id": getattr(m, "mapID", None),
                    "name": getattr(m, "name", None),
                }
                for m in supported_maps
            ]

        return {
            "areas": areas,
            "maps": maps,
        }

    async def async_handle_get_areas(self, **kwargs: Any) -> ServiceResponse:
        """Get available area and map IDs from vacuum appliance."""
        # Group by area_id: {area_id: {"map_id": ..., "name": ...}}
        areas = {}
        if self._attr_matter_areas is not None:
            for area in self._attr_matter_areas:
                area_id = getattr(area, "areaID", None)
                map_id = getattr(area, "mapID", None)
                location_name = None
                area_info = getattr(area, "areaInfo", None)
                if area_info is not None:
                    location_info = getattr(area_info, "locationInfo", None)
                    if location_info is not None:
                        location_name = getattr(location_info, "locationName", None)
                if area_id is not None:
                    if map_id is NullValue:
                        areas[area_id] = {"name": location_name}
                    else:
                        areas[area_id] = {"map_id": map_id, "name": location_name}

            # Optionally, also extract supported maps if available
            supported_maps = self.get_matter_attribute_value(
                clusters.ServiceArea.Attributes.SupportedMaps
            )
            maps = []
            if supported_maps != NullValue:  # chip.clusters.Types.Nullable
                maps = [
                    {
                        "map_id": getattr(m, "mapID", None)
                        if getattr(m, "mapID", None) != NullValue
                        else None,
                        "name": getattr(m, "name", None),
                    }
                    for m in supported_maps
                ]

            return cast(
                ServiceResponse,
                {
                    "areas": areas,
                    "maps": maps,
                },
            )
        return None

    async def async_handle_select_areas(
        self, areas: list[int], **kwargs: Any
    ) -> ServiceResponse:
        """Select areas to clean."""
        selected_areas = areas
        # Matter command to the vacuum cleaner to select the areas.
        await self.send_device_command(
            clusters.ServiceArea.Commands.SelectAreas(newAreas=selected_areas)
        )
        # Return response indicating selected areas.
        return cast(
            ServiceResponse, {"status": "areas selected", "areas": selected_areas}
        )

    async def async_handle_clean_areas(
        self, areas: list[int], **kwargs: Any
    ) -> ServiceResponse:
        """Start cleaning the specified areas."""
        # Matter command to the vacuum cleaner to select the areas.
        await self.send_device_command(
            clusters.ServiceArea.Commands.SelectAreas(newAreas=areas)
        )
        # Start the vacuum cleaner after selecting areas.
        await self.async_start()
        # Return response indicating selected areas.
        return cast(
            ServiceResponse, {"status": "cleaning areas selected", "areas": areas}
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        # ServiceArea: get areas from the device
        self._attr_matter_areas = self.get_matter_attribute_value(
            clusters.ServiceArea.Attributes.SupportedAreas
        )
        # optional CurrentArea attribute
        # pylint: disable=too-many-nested-blocks
        if self.get_matter_attribute_value(clusters.ServiceArea.Attributes.CurrentArea):
            current_area = self.get_matter_attribute_value(
                clusters.ServiceArea.Attributes.CurrentArea
            )
            # get areaInfo.locationInfo.locationName for current_area in SupportedAreas list
            area_name = None
            if self._attr_matter_areas:
                for area in self._attr_matter_areas:
                    if getattr(area, "areaID", None) == current_area:
                        area_info = getattr(area, "areaInfo", None)
                        if area_info is not None:
                            location_info = getattr(area_info, "locationInfo", None)
                            if location_info is not None:
                                area_name = getattr(location_info, "locationName", None)
                        break
            self._attr_current_area = current_area
            self._attr_current_area_name = area_name
        else:
            self._attr_current_area = None
            self._attr_current_area_name = None

        # optional SelectedAreas attribute
        if self.get_matter_attribute_value(
            clusters.ServiceArea.Attributes.SelectedAreas
        ):
            self._attr_selected_areas = self.get_matter_attribute_value(
                clusters.ServiceArea.Attributes.SelectedAreas
            )
        # derive state from the run mode + operational state
        run_mode_raw: int = self.get_matter_attribute_value(
            clusters.RvcRunMode.Attributes.CurrentMode
        )
        operational_state: int = self.get_matter_attribute_value(
            clusters.RvcOperationalState.Attributes.OperationalState
        )
        state: VacuumActivity | None = None
        if TYPE_CHECKING:
            assert self._supported_run_modes is not None
        if operational_state in (OperationalState.CHARGING, OperationalState.DOCKED):
            state = VacuumActivity.DOCKED
        elif operational_state == OperationalState.SEEKING_CHARGER:
            state = VacuumActivity.RETURNING
        elif operational_state == OperationalState.ERROR:
            state = VacuumActivity.ERROR
        elif operational_state == OperationalState.PAUSED:
            state = VacuumActivity.PAUSED
        elif (run_mode := self._supported_run_modes.get(run_mode_raw)) is not None:
            tags = {x.value for x in run_mode.modeTags}
            if ModeTag.CLEANING in tags:
                state = VacuumActivity.CLEANING
            elif ModeTag.IDLE in tags:
                state = VacuumActivity.IDLE
            elif ModeTag.MAPPING in tags:
                state = VacuumActivity.CLEANING
        self._attr_activity = state

    @callback
    def _calculate_features(self) -> None:
        """Calculate features for HA Vacuum platform."""
        accepted_operational_commands: list[int] = self.get_matter_attribute_value(
            clusters.RvcOperationalState.Attributes.AcceptedCommandList
        )
        # in principle the feature set should not change, except for the accepted commands
        if self._last_accepted_commands == accepted_operational_commands:
            return
        self._last_accepted_commands = accepted_operational_commands
        supported_features: VacuumEntityFeature = VacuumEntityFeature(0)
        supported_features |= VacuumEntityFeature.START
        supported_features |= VacuumEntityFeature.STATE
        supported_features |= VacuumEntityFeature.STOP

        # optional identify cluster = locate feature (value must be not None or 0)
        if self.get_matter_attribute_value(clusters.Identify.Attributes.IdentifyType):
            supported_features |= VacuumEntityFeature.LOCATE
        # create a map of supported run modes
        run_modes: list[clusters.RvcRunMode.Structs.ModeOptionStruct] = (
            self.get_matter_attribute_value(
                clusters.RvcRunMode.Attributes.SupportedModes
            )
        )
        self._supported_run_modes = {mode.mode: mode for mode in run_modes}
        # map operational state commands to vacuum features
        if (
            clusters.RvcOperationalState.Commands.Pause.command_id
            in accepted_operational_commands
        ):
            supported_features |= VacuumEntityFeature.PAUSE
        if (
            clusters.RvcOperationalState.Commands.GoHome.command_id
            in accepted_operational_commands
        ):
            supported_features |= VacuumEntityFeature.RETURN_HOME

        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.VACUUM,
        entity_description=StateVacuumEntityDescription(
            key="MatterVacuumCleaner", name=None
        ),
        entity_class=MatterVacuum,
        required_attributes=(
            clusters.RvcRunMode.Attributes.CurrentMode,
            clusters.RvcOperationalState.Attributes.OperationalState,
        ),
        optional_attributes=(
            clusters.ServiceArea.Attributes.SelectedAreas,
            clusters.ServiceArea.Attributes.CurrentArea,
        ),
        device_type=(device_types.RoboticVacuumCleaner,),
        allow_none_value=True,
    ),
]
