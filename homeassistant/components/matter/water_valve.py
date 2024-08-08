"""Matter water valve."""

from __future__ import annotations

from enum import IntEnum
from math import floor
from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.components.valve import (
    ATTR_POSITION,
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

# The MASK used for extracting bits 0 to 1 of the byte.
OPERATIONAL_STATUS_MASK = 0b11

# map Matter valve types to HA device class
'''
TYPE_MAP = {
    clusters.ValveConfigurationAndControl.Enums.Type.kWater: ValveDeviceClass.WATER, // TODO
    #clusters.ValveConfigurationAndControl.Enums.Type.kDrapery: ValveDeviceClass.GAS,
}
'''

# ValveStateEnum
class OperationalStatus(IntEnum):
    """Currently ongoing operations enumeration for water valve, as defined in the Matter spec."""

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
    '''
    async def async_stop_water_valve(self, **kwargs: Any) -> None:
        """Stop the water valve movement."""
        await self.send_device_command(clusters.ValveConfigurationAndControl.Commands.StopMotion())
    '''

    async def async_open_water_valve(self, **kwargs: Any) -> None:
        """Open the water valve."""
        await self.send_device_command(clusters.ValveConfigurationAndControl.Commands.Open())

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the water valve."""
        await self.send_device_command(clusters.ValveConfigurationAndControl.Commands.Close())

    async def async_set_valve_position(self, **kwargs: Any) -> None:
        """Set the water valve to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self.send_device_command(
            # A value of 100 percent SHALL indicate the fully open position
            # A value of 0 percent SHALL indicate the fully closed position
            # A value of null SHALL indicate that the current state is not known
            clusters.ValveConfigurationAndControl.Commands.Open(position) # TargetLevel type="percent"
        )

    async def send_device_command(self, command: Any) -> None:
        """Send device command."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        operational_status = self.get_matter_attribute_value(
            clusters.ValveConfigurationAndControl.Attributes.OperationalStatus
        )

        assert operational_status is not None

        LOGGER.debug(
            "Operational status %s for %s",
            f"{operational_status:#010b}",
            self.entity_id,
        )

        state = operational_status & OPERATIONAL_STATUS_MASK
        match state:
            # Valve is transitioning between closed and open positions or between levels
            case OperationalStatus.VALVE_IS_CURRENTLY_TRANSITIONING:
                self._attr_is_opening = True
                #self._attr_is_closing = False
                #self._attr_is_transitioning = True --> Not implemented here: https://developers.home-assistant.io/docs/core/entity/valve
            case _:
                self._attr_is_opening = False
                self._attr_is_closing = False

        if self._entity_info.endpoint.has_attribute(
            None, clusters.ValveConfigurationAndControl.Attributes.CurrentLevel
        ):

            # A value of 100 percent SHALL indicate the fully open position
            # A value of 0 percent SHALL indicate the fully closed position
            # A value of null SHALL indicate that the current state is not known
            current_valve_position = self.get_matter_attribute_value(
                clusters.ValveConfigurationAndControl.Attributes.CurrentLevel
            )
            self._attr_current_valve_position = (
                floor(current_valve_position / 100)
                if current_valve_position is not None
                else None
            )

            LOGGER.debug(
                "Current position for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_valve_position,
                self.current_valve_position,
            )


        # map matter type to HA deviceclass
        device_type: clusters.ValveConfigurationAndControl.Enums.Type = (
            self.get_matter_attribute_value(clusters.ValveConfigurationAndControl.Attributes.Type)
        )
        self._attr_device_class = TYPE_MAP.get(device_type, ValveDeviceClass.WATER)

        supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )
        commands = self.get_matter_attribute_value(
            clusters.ValveConfigurationAndControl.Attributes.AcceptedCommandList
        )
        if clusters.ValveConfigurationAndControl.Commands.Open.command_id in commands:
            supported_features |= ValveEntityFeature.SET_POSITION
        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISVALVEY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.VALVE,
        entity_description=ValveEntityDescription(
            key="MatterValve", translation_key="valve"
        ),
        entity_class=MatterValve,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.OperationalStatus,
            clusters.ValveConfigurationAndControl.Attributes.OpenDuration,
            clusters.ValveConfigurationAndControl.Attributes.DefaultOpenDuration,
            clusters.ValveConfigurationAndControl.Attributes.RemainingDuration,
            clusters.ValveConfigurationAndControl.Attributes.CurrentState,
            clusters.ValveConfigurationAndControl.Attributes.TargetState,
        ),
        absent_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.CurrentLevel,
            clusters.ValveConfigurationAndControl.Attributes.TargetLevel,
        ),
    ),
]
