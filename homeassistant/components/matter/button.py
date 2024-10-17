"""Matter Button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Button platform."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BUTTON, async_add_entities)


@dataclass(frozen=True)
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
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=self.entity_description.command(),
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="IdentifyButton",
            entity_category=EntityCategory.CONFIG,
            device_class=ButtonDeviceClass.IDENTIFY,
            command=lambda: clusters.Identify.Commands.Identify(identifyTime=15),
        ),
        entity_class=MatterCommandButton,
        required_attributes=(clusters.Identify.Attributes.AcceptedCommandList,),
        value_contains=clusters.Identify.Commands.Identify.command_id,
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
]
