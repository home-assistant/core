"""Matter Button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter Button platform."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BUTTON, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterButtonEntityDescription(ButtonEntityDescription, MatterEntityDescription):
    """Describe Matter Button entities."""

    command: Callable[[], Any] | None = None


class MatterCommandButton(MatterEntity, ButtonEntity):
    """Representation of a Matter Button entity."""

    entity_description: MatterButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press leveraging a Matter command."""
        if TYPE_CHECKING:
            assert self.entity_description.command is not None
        await self.send_device_command(self.entity_description.command())


# CHIP epoch: 2000-01-01 00:00:00 UTC
CHIP_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


class MatterTimeSyncButton(MatterEntity, ButtonEntity):
    """Button to synchronize time to a Matter device."""

    entity_description: MatterButtonEntityDescription

    async def async_press(self) -> None:
        """Sync Home Assistant time to the Matter device."""
        now = dt_util.utcnow()
        tz = dt_util.get_default_time_zone()
        delta = now - CHIP_EPOCH
        utc_us = (
            (delta.days * 86400 * 1_000_000)
            + (delta.seconds * 1_000_000)
            + delta.microseconds
        )

        # Compute timezone and DST offsets
        local_now = now.astimezone(tz)
        utc_offset_delta = local_now.utcoffset()
        utc_offset = int(utc_offset_delta.total_seconds()) if utc_offset_delta else 0
        dst_offset_delta = local_now.dst()
        dst_offset = int(dst_offset_delta.total_seconds()) if dst_offset_delta else 0
        standard_offset = utc_offset - dst_offset

        # 1. Set timezone
        await self.send_device_command(
            clusters.TimeSynchronization.Commands.SetTimeZone(
                timeZone=[
                    clusters.TimeSynchronization.Structs.TimeZoneStruct(
                        offset=standard_offset, validAt=0, name=str(tz)
                    )
                ]
            )
        )

        # 2. Set DST offset
        await self.send_device_command(
            clusters.TimeSynchronization.Commands.SetDSTOffset(
                DSTOffset=[
                    clusters.TimeSynchronization.Structs.DSTOffsetStruct(
                        offset=dst_offset,
                        validStarting=0,
                        validUntil=NullValue,
                    )
                ]
            )
        )

        # 3. Set UTC time
        await self.send_device_command(
            clusters.TimeSynchronization.Commands.SetUTCTime(
                UTCTime=utc_us,
                granularity=clusters.TimeSynchronization.Enums.GranularityEnum.kMicrosecondsGranularity,
            )
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="IdentifyButton",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=ButtonDeviceClass.IDENTIFY,
            command=lambda: clusters.Identify.Commands.Identify(identifyTime=15),
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.Identify.Attributes.IdentifyType,),
        value_is_not=clusters.Identify.Enums.IdentifyTypeEnum.kNone,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="OperationalStatePauseButton",
            translation_key="pause",
            command=clusters.OperationalState.Commands.Pause,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.OperationalState.Attributes.AcceptedCommandList,),
        value_contains=clusters.OperationalState.Commands.Pause.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="OperationalStateResumeButton",
            translation_key="resume",
            command=clusters.OperationalState.Commands.Resume,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.OperationalState.Attributes.AcceptedCommandList,),
        value_contains=clusters.OperationalState.Commands.Resume.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="OperationalStateStartButton",
            translation_key="start",
            command=clusters.OperationalState.Commands.Start,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.OperationalState.Attributes.AcceptedCommandList,),
        value_contains=clusters.OperationalState.Commands.Start.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="OperationalStateStopButton",
            translation_key="stop",
            command=clusters.OperationalState.Commands.Stop,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.OperationalState.Attributes.AcceptedCommandList,),
        value_contains=clusters.OperationalState.Commands.Stop.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="HepaFilterMonitoringResetButton",
            translation_key="reset_filter_condition",
            command=clusters.HepaFilterMonitoring.Commands.ResetCondition,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(
            clusters.HepaFilterMonitoring.Attributes.AcceptedCommandList,
        ),
        value_contains=clusters.HepaFilterMonitoring.Commands.ResetCondition.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="ActivatedCarbonFilterMonitoringResetButton",
            translation_key="reset_filter_condition",
            command=clusters.ActivatedCarbonFilterMonitoring.Commands.ResetCondition,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(
            clusters.ActivatedCarbonFilterMonitoring.Attributes.AcceptedCommandList,
        ),
        value_contains=clusters.ActivatedCarbonFilterMonitoring.Commands.ResetCondition.command_id,
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="SmokeCoAlarmSelfTestRequest",
            translation_key="self_test_request",
            entity_category=EntityCategory.DIAGNOSTIC,
            command=clusters.SmokeCoAlarm.Commands.SelfTestRequest,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.AcceptedCommandList,),
        value_contains=clusters.SmokeCoAlarm.Commands.SelfTestRequest.command_id,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="WaterHeaterManagementCancelBoost",
            translation_key="cancel_boost",
            command=clusters.WaterHeaterManagement.Commands.CancelBoost,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(
            clusters.WaterHeaterManagement.Attributes.AcceptedCommandList,
        ),
        value_contains=clusters.WaterHeaterManagement.Commands.CancelBoost.command_id,
        allow_multi=True,  # Also used in water_heater
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="TimeSynchronizationSyncTimeButton",
            translation_key="sync_time",
            entity_category=EntityCategory.CONFIG,
        ),
        entity_class=MatterTimeSyncButton,
        required_attributes=(clusters.TimeSynchronization.Attributes.UTCTime,),
        allow_multi=True,
        allow_none_value=True,
    ),
]
