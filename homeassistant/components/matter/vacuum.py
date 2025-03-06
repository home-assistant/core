"""Matter vacuum platform."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


class OperationalState(IntEnum):
    """Operational State of the vacuum cleaner.

    Combination of generic OperationalState and RvcOperationalState.
    """

    NO_ERROR = 0x00
    UNABLE_TO_START_OR_RESUME = 0x01
    UNABLE_TO_COMPLETE_OPERATION = 0x02
    COMMAND_INVALID_IN_STATE = 0x03
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


class MatterVacuum(MatterEntity, StateVacuumEntity):
    """Representation of a Matter Vacuum cleaner entity."""

    _last_accepted_commands: list[int] | None = None
    _supported_run_modes: (
        dict[int, clusters.RvcCleanMode.Structs.ModeOptionStruct] | None
    ) = None
    entity_description: StateVacuumEntityDescription
    _platform_translation_key = "vacuum"

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.send_device_command(clusters.OperationalState.Commands.Stop())

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
        if (
            clusters.RvcOperationalState.Commands.Resume.command_id
            in self._last_accepted_commands
        ):
            await self.send_device_command(
                clusters.RvcOperationalState.Commands.Resume()
            )
        else:
            await self.send_device_command(clusters.OperationalState.Commands.Start())

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_device_command(clusters.OperationalState.Commands.Pause())

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        # optional battery level
        if VacuumEntityFeature.BATTERY & self._attr_supported_features:
            self._attr_battery_level = self.get_matter_attribute_value(
                clusters.PowerSource.Attributes.BatPercentRemaining
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
        elif operational_state in (
            OperationalState.UNABLE_TO_COMPLETE_OPERATION,
            OperationalState.UNABLE_TO_START_OR_RESUME,
        ):
            state = VacuumActivity.ERROR
        elif (run_mode := self._supported_run_modes.get(run_mode_raw)) is not None:
            tags = {x.value for x in run_mode.modeTags}
            if ModeTag.CLEANING in tags:
                state = VacuumActivity.CLEANING
            elif ModeTag.IDLE in tags:
                state = VacuumActivity.IDLE
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
        supported_features |= VacuumEntityFeature.STATE
        # optional battery attribute = battery feature
        if self.get_matter_attribute_value(
            clusters.PowerSource.Attributes.BatPercentRemaining
        ):
            supported_features |= VacuumEntityFeature.BATTERY
        # optional identify cluster = locate feature (value must be not None or 0)
        if self.get_matter_attribute_value(clusters.Identify.Attributes.IdentifyType):
            supported_features |= VacuumEntityFeature.LOCATE
        # create a map of supported run modes
        run_modes: list[clusters.RvcCleanMode.Structs.ModeOptionStruct] = (
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
            clusters.OperationalState.Commands.Stop.command_id
            in accepted_operational_commands
        ):
            supported_features |= VacuumEntityFeature.STOP
        if (
            clusters.OperationalState.Commands.Start.command_id
            in accepted_operational_commands
        ):
            # note that start has been replaced by resume in rev2 of the spec
            supported_features |= VacuumEntityFeature.START
        if (
            clusters.RvcOperationalState.Commands.Resume.command_id
            in accepted_operational_commands
        ):
            supported_features |= VacuumEntityFeature.START
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
            clusters.RvcOperationalState.Attributes.CurrentPhase,
        ),
        optional_attributes=(
            clusters.RvcCleanMode.Attributes.CurrentMode,
            clusters.PowerSource.Attributes.BatPercentRemaining,
        ),
        device_type=(device_types.RoboticVacuumCleaner,),
        allow_none_value=True,
    ),
]
