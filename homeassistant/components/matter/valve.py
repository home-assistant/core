"""Matter water valve."""

from __future__ import annotations

from enum import IntEnum

from chip.clusters import Objects as clusters

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

from .const import LOGGER
from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

ValveConfigurationAndControlFeature = (
    clusters.ValveConfigurationAndControl.Bitmaps.Feature
)

# The MASK used for extracting bits 0 to 1 of the byte.
CURRENT_STATE_MASK = 0b11


# ValveStateEnum
class CurrentState(IntEnum):
    """Currently ongoing operations enumeration for Matter water valve."""

    VALVE_IS_CURRENTLY_CLOSED = 0b00
    VALVE_IS_CURRENTLY_OPEN = 0b01
    VALVE_IS_CURRENTLY_TRANSITIONING = 0b10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter water valve from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.VALVE, async_add_entities)


class MatterValve(MatterEntity, ValveEntity):
    """Representation of a Matter Valve."""

    _feature_map: int | None = None
    entity_description: ValveEntityDescription

    @property
    def is_closed(self) -> bool | None:
        """Return true if water valve is closed, if there is no position report, return None."""
        if not self._entity_info.endpoint.has_attribute(
            None, clusters.ValveConfigurationAndControl.Attributes.CurrentLevel
        ):
            return None

        return (
            self.current_valve_position == 0
            if self.current_valve_position is not None
            else None
        )

    async def send_device_command(
        self,
        command: clusters.ClusterCommand,
        timed_request_timeout_ms: int = 1000,
    ) -> None:
        """Send a command to the device."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
            timed_request_timeout_ms=timed_request_timeout_ms,
        )

    async def async_open_water_valve(self) -> None:
        """Open the water valve."""
        await self.send_device_command(
            clusters.ValveConfigurationAndControl.Commands.Open()
        )

    async def async_close_valve(self) -> None:
        """Close the water valve."""
        await self.send_device_command(
            clusters.ValveConfigurationAndControl.Commands.Close()
        )

    async def async_set_valve_position(self, position: int) -> None:
        """Move the water valve to a specific position."""
        await self.send_device_command(
            # A value of 100 percent SHALL indicate the fully open position
            # A value of 0 percent SHALL indicate the fully closed position
            # A value of null SHALL indicate that the current state is not known
            clusters.ValveConfigurationAndControl.Commands.Open(
                position
            )  # TargetLevel type="percent"
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        current_state = self.get_matter_attribute_value(
            clusters.ValveConfigurationAndControl.Attributes.CurrentState
        )

        assert current_state is not None

        LOGGER.debug(
            "Current state %s for %s",
            f"{current_state:#010b}",
            self.entity_id,
        )

        state = current_state & CURRENT_STATE_MASK
        match state:
            # Valve is transitioning between closed and open positions or between levels
            case CurrentState.VALVE_IS_CURRENTLY_TRANSITIONING:
                self._attr_is_opening = True
            case _:
                self._attr_is_opening = False
                self._attr_is_closing = False

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA Valve platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(
                clusters.ValveConfigurationAndControl.Attributes.FeatureMap
            )
        )

        # NOTE: the featuremap can dynamically change, so we need to update the
        # supported features if the featuremap changes.
        # work out supported features and presets from matter featuremap
        if self._feature_map == feature_map:
            return
        self._feature_map = feature_map
        self._attr_supported_features = ValveEntityFeature(0)
        if feature_map & ValveConfigurationAndControlFeature.kLevel:
            self._attr_supported_features |= ValveEntityFeature.SET_POSITION

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
            clusters.ValveConfigurationAndControl.Attributes.OpenDuration,
            clusters.ValveConfigurationAndControl.Attributes.DefaultOpenDuration,
            clusters.ValveConfigurationAndControl.Attributes.RemainingDuration,
            clusters.ValveConfigurationAndControl.Attributes.CurrentState,
            clusters.ValveConfigurationAndControl.Attributes.TargetState,
        ),
    ),
]
