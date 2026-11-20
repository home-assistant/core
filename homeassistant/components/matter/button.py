"""Matter Button platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, override

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.custom_clusters import HeimanCluster

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BORDER_ROUTER_DEVICE_TYPES
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema
from .wifi_credentials import async_import_credentials


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter Button platform."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.BUTTON, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterButtonEntityDescription(ButtonEntityDescription, MatterEntityDescription):
    """Describe Matter Button entities."""

    command: Callable[[], Any] | None = None


class MatterCommandButton(MatterEntity, ButtonEntity):
    """Representation of a Matter Button entity."""

    entity_description: MatterButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Handle the button press leveraging a Matter command."""
        if TYPE_CHECKING:
            assert self.entity_description.command is not None
        await self.send_device_command(self.entity_description.command())


async def _async_require_admin(hass: HomeAssistant, context: Context | None) -> None:
    """Refuse a press by a user who is not an administrator.

    As for an admin-only action, a press without a user, from an automation,
    passes.
    """
    if context is None or context.user_id is None:
        return
    user = await hass.auth.async_get_user(context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=context)


class MatterThreadDatasetImportButton(MatterEntity, ButtonEntity):
    """Button importing a Thread border router's dataset into Home Assistant."""

    @override
    async def async_press(self) -> None:
        """Import the dataset, which holds the network key."""
        await _async_require_admin(self.hass, self._context)
        entry = cast(MatterConfigEntry, self.platform.config_entry)
        await entry.runtime_data.thread_datasets.async_import(self._endpoint)


class MatterWifiCredentialsImportButton(MatterEntity, ButtonEntity):
    """Button handing a network manager's Wi-Fi credentials to the Matter server."""

    @override
    async def async_press(self) -> None:
        """Import the credentials, replacing the server's."""
        await _async_require_admin(self.hass, self._context)
        await async_import_credentials(self.matter_client, self._endpoint)


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="ThreadDatasetImportButton",
            translation_key="import_thread_network",
            entity_category=EntityCategory.CONFIG,
        ),
        entity_class=MatterThreadDatasetImportButton,
        required_attributes=(
            clusters.ThreadBorderRouterManagement.Attributes.ActiveDatasetTimestamp,
        ),
        device_type=BORDER_ROUTER_DEVICE_TYPES,
        # Null while the router has no network; the button stays.
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BUTTON,
        entity_description=MatterButtonEntityDescription(
            key="WifiCredentialsImportButton",
            translation_key="import_wifi_credentials",
            entity_category=EntityCategory.CONFIG,
        ),
        entity_class=MatterWifiCredentialsImportButton,
        required_attributes=(clusters.WiFiNetworkManagement.Attributes.Ssid,),
        device_type=(device_types.NetworkInfrastructureManager,),
        # Null while sharing is off; the button stays.
        allow_none_value=True,
    ),
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
            key="HeimanSmokeCoAlarmTemporaryMuteRequest",
            translation_key="temporary_mute_request",
            command=HeimanCluster.Commands.MutingSensor,
        ),
        entity_class=MatterCommandButton,
        required_attributes=(HeimanCluster.Attributes.AcceptedCommandList,),
        value_contains=HeimanCluster.Commands.MutingSensor.command_id,
    ),
]
