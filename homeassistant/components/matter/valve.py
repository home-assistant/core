"""Matter valve platform."""

from __future__ import annotations

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

ValveConfigurationAndControl = clusters.ValveConfigurationAndControl

ValveStateEnum = ValveConfigurationAndControl.Enums.ValveStateEnum


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter valve platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.VALVE, async_add_entities)


class MatterValve(MatterEntity, ValveEntity):
    """Representation of a Matter Valve."""

    _feature_map: int | None = None
    entity_description: ValveEntityDescription

    async def send_device_command(
        self,
        command: clusters.ClusterCommand,
    ) -> None:
        """Send a command to the device."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
        )

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.send_device_command(ValveConfigurationAndControl.Commands.Open())

    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.send_device_command(ValveConfigurationAndControl.Commands.Close())

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self.send_device_command(
            ValveConfigurationAndControl.Commands.Open(targetLevel=position)
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        current_state: int
        current_state = self.get_matter_attribute_value(
            ValveConfigurationAndControl.Attributes.CurrentState
        )
        target_state: int
        target_state = self.get_matter_attribute_value(
            ValveConfigurationAndControl.Attributes.TargetState
        )
        if (
            current_state == ValveStateEnum.kTransitioning
            and target_state == ValveStateEnum.kOpen
        ):
            self._attr_is_opening = True
            self._attr_is_closing = False
        elif (
            current_state == ValveStateEnum.kTransitioning
            and target_state == ValveStateEnum.kClosed
        ):
            self._attr_is_opening = False
            self._attr_is_closing = True
        elif current_state == ValveStateEnum.kClosed:
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._attr_is_closed = True
        else:
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._attr_is_closed = False
        # handle optional position
        if self.supported_features & ValveEntityFeature.SET_POSITION:
            self._attr_current_valve_position = self.get_matter_attribute_value(
                ValveConfigurationAndControl.Attributes.CurrentLevel
            )

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA Valve platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(
                ValveConfigurationAndControl.Attributes.FeatureMap
            )
        )
        # NOTE: the featuremap can dynamically change, so we need to update the
        # supported features if the featuremap changes.
        # work out supported features and presets from matter featuremap
        if self._feature_map == feature_map:
            return
        self._feature_map = feature_map
        self._attr_supported_features = ValveEntityFeature(0)
        if feature_map & ValveConfigurationAndControl.Bitmaps.Feature.kLevel:
            self._attr_supported_features |= ValveEntityFeature.SET_POSITION
            self._attr_reports_position = True
        else:
            self._attr_reports_position = False

        self._attr_supported_features |= (
            ValveEntityFeature.CLOSE | ValveEntityFeature.OPEN
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.VALVE,
        entity_description=ValveEntityDescription(
            key="MatterValve",
            device_class=ValveDeviceClass.WATER,
            translation_key="valve",
        ),
        entity_class=MatterValve,
        required_attributes=(
            ValveConfigurationAndControl.Attributes.CurrentState,
            ValveConfigurationAndControl.Attributes.TargetState,
        ),
        optional_attributes=(ValveConfigurationAndControl.Attributes.CurrentLevel,),
        device_type=(device_types.WaterValve,),
    ),
]
