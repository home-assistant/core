"""Matter vacuum platform."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import logging
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema

_LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True, kw_only=True)
class MatterStateVacuumEntityDescription(
    StateVacuumEntityDescription, MatterEntityDescription
):
    """Describe Matter Vacuum entities."""


class MatterVacuum(MatterEntity, StateVacuumEntity):
    """Representation of a Matter Vacuum cleaner entity."""

    _last_accepted_commands: list[int] | None = None
    _last_service_area_feature_map: int | None = None
    _supported_run_modes: (
        dict[int, clusters.RvcRunMode.Structs.ModeOptionStruct] | None
    ) = None
    entity_description: MatterStateVacuumEntityDescription
    _platform_translation_key = "vacuum"

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

        # Reset selected areas to an unconstrained selection to ensure start
        # performs a full clean and does not reuse a previous area-targeted
        # selection.
        if VacuumEntityFeature.CLEAN_AREA in self.supported_features:
            # Matter ServiceArea: an empty NewAreas list means unconstrained
            # operation (full clean).
            await self.send_device_command(
                clusters.ServiceArea.Commands.SelectAreas(newAreas=[])
            )

        await self.send_device_command(
            clusters.RvcRunMode.Commands.ChangeToMode(newMode=mode.mode)
        )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_device_command(clusters.RvcOperationalState.Commands.Pause())

    @property
    def _current_segments(self) -> dict[str, Segment]:
        """Return the current cleanable segments reported by the device."""
        supported_areas: list[clusters.ServiceArea.Structs.AreaStruct] = (
            self.get_matter_attribute_value(
                clusters.ServiceArea.Attributes.SupportedAreas
            )
        )

        segments: dict[str, Segment] = {}
        for area in supported_areas:
            area_name = None
            location_info = area.areaInfo.locationInfo
            if location_info not in (None, clusters.NullValue):
                area_name = location_info.locationName

            if area_name:
                segment_id = str(area.areaID)
                segments[segment_id] = Segment(id=segment_id, name=area_name)

        return segments

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned.

        Returns a list of segments containing their ids and names.
        """
        return list(self._current_segments.values())

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments.

        Args:
            segment_ids: List of segment IDs to clean.
            **kwargs: Additional arguments (unused).

        """
        area_ids = [int(segment_id) for segment_id in segment_ids]

        mode = self._get_run_mode_by_tag(ModeTag.CLEANING)
        if mode is None:
            raise HomeAssistantError(
                "No supported run mode found to start the vacuum cleaner."
            )

        response = await self.send_device_command(
            clusters.ServiceArea.Commands.SelectAreas(newAreas=area_ids)
        )

        if (
            response
            and response["status"]
            != clusters.ServiceArea.Enums.SelectAreasStatus.kSuccess
        ):
            raise HomeAssistantError(
                f"Failed to select areas: {response['statusText'] or response['status']}"
            )

        await self.send_device_command(
            clusters.RvcRunMode.Commands.ChangeToMode(newMode=mode.mode)
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
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

        if (
            VacuumEntityFeature.CLEAN_AREA in self.supported_features
            and self.registry_entry is not None
            and (last_seen_segments := self.last_seen_segments) is not None
            # Ignore empty segments; some devices transiently
            # report an empty list before sending the real one.
            and (current_segments := self._current_segments)
        ):
            last_seen_by_id = {s.id: s for s in last_seen_segments}
            if current_segments != last_seen_by_id:
                _LOGGER.debug(
                    "Vacuum segments changed: last_seen=%s, current=%s",
                    last_seen_by_id,
                    current_segments,
                )
                self.async_create_segments_issue()

    @callback
    def _calculate_features(self) -> None:
        """Calculate features for HA Vacuum platform."""
        accepted_operational_commands: list[int] = self.get_matter_attribute_value(
            clusters.RvcOperationalState.Attributes.AcceptedCommandList
        )
        service_area_feature_map: int | None = self.get_matter_attribute_value(
            clusters.ServiceArea.Attributes.FeatureMap
        )

        # In principle the feature set should not change, except for accepted
        # commands and service area feature map.
        if (
            self._last_accepted_commands == accepted_operational_commands
            and self._last_service_area_feature_map == service_area_feature_map
        ):
            return

        self._last_accepted_commands = accepted_operational_commands
        self._last_service_area_feature_map = service_area_feature_map
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
        # Check if Map feature is enabled for clean area support
        if (
            service_area_feature_map is not None
            and service_area_feature_map & clusters.ServiceArea.Bitmaps.Feature.kMaps
        ):
            supported_features |= VacuumEntityFeature.CLEAN_AREA

        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.VACUUM,
        entity_description=MatterStateVacuumEntityDescription(
            key="MatterVacuumCleaner", name=None
        ),
        entity_class=MatterVacuum,
        required_attributes=(
            clusters.RvcRunMode.Attributes.CurrentMode,
            clusters.RvcOperationalState.Attributes.OperationalState,
        ),
        optional_attributes=(
            clusters.ServiceArea.Attributes.FeatureMap,
            clusters.ServiceArea.Attributes.SupportedAreas,
        ),
        device_type=(device_types.RoboticVacuumCleaner,),
        allow_none_value=True,
    ),
]
