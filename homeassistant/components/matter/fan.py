"""Matter fan."""
from __future__ import annotations

from enum import IntEnum
from math import floor
from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    FanEntity,
    FanEntityFeature,
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

# map Matter fan types to HA device class
# TODO replace by Fan
TYPE_MAP = {
    clusters.FanControl: fan # homeassistant.components.fan
}

'''
// Fan control cluster attributes
DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(fanControlAttrs)
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::FanMode::Id, INT8U, 1, ATTRIBUTE_MASK_WRITABLE),            /* FanMode */
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::FanModeSequence::Id, INT8U, 1, 0),                          /* FanModeSequence */
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::PercentSetting::Id, INT8U, 1, ATTRIBUTE_MASK_WRITABLE),     /* PercentSetting */
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::PercentCurrent::Id, INT8U, 1, 0),                           /* PercentCurrent */
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::FeatureMap::Id, BITMAP32, 4, 0),                            /* FeatureMap */
DECLARE_DYNAMIC_ATTRIBUTE(FanControl::Attributes::ClusterRevision::Id, INT16U, 2, 0),                         /* ClusterRevision */
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// Fan control endpoint cluster list
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(fanControlEndpointClusters)
DECLARE_DYNAMIC_CLUSTER(FanControl::Id, fanControlAttrs, nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER(Descriptor::Id, descriptorAttrsFanControl, nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER_LIST_END;
'''

class OperationalStatus(IntEnum):
    """Currently ongoing operations enumeration for fan, as defined in the Matter spec."""

    FAN_IS_CURRENTLY_OFF = 0b00    # Fan is off
    FAN_IS_CURRENTLY_LOW = 0b01    # Fan using low speed
    FAN_IS_CURRENTLY_MEDIUM = 0b02  # Fan using high speed
    FAN_IS_CURRENTLY_HIGH = 0b03    # Fan using high speed
    FAN_IS_CURRENTLY_ON = 0b04      # Fan is on
    FAN_IS_CURRENTLY_AUTO = 0b05    # Fan is using auto mode
    FAN_IS_CURRENTLY_SMART = 0b06   # Fan is using smart mode

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Fan from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.FAN, async_add_entities)


class MatterFan(MatterEntity, FanEntity):
    """Representation of a Matter Fan."""

    entity_description: FanEntityDescription

    @property
    def is_closed(self) -> bool | None:
        """Return true if fan is closed, if there is no position report, return None."""
        if not self._entity_info.endpoint.has_attribute(
            None, clusters.Fan.Attributes.PercentCurrent
        ):
            return None

        return (
            self.current_percent == 0
            if self.current_percent is not None
            else None
        )

    async def async_stop_fan(self, **kwargs: Any) -> None:
        """Stop the fan movement."""
        await self.send_device_command(clusters.Fan.Commands.StopMotion())

    async def async_open_fan(self, **kwargs: Any) -> None:
        """Open the fan."""
        await self.send_device_command(clusters.Fan.Commands.UpOrOpen())

    async def async_close_fan(self, **kwargs: Any) -> None:
        """Close the fan."""
        await self.send_device_command(clusters.Fan.Commands.DownOrClose())

    async def async_set_fan_percent(self, **kwargs: Any) -> None:
        """Set the fan to a specific position."""
        position = kwargs[ATTR_PERCENT]
        await self.send_device_command(
            clusters.Fan.Commands.Step(position)
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
            clusters.Fan.Attributes.OperationalStatus
        )

        assert operational_status is not None

        LOGGER.debug(
            "Operational status %s for %s",
            f"{operational_status:#010b}",
            self.entity_id,
        )

        state = operational_status & OPERATIONAL_STATUS_MASK
        match state:
            case OperationalStatus.COVERING_IS_CURRENTLY_OPENING:
                self._attr_is_opening = True
                self._attr_is_closing = False
            case OperationalStatus.COVERING_IS_CURRENTLY_CLOSING:
                self._attr_is_opening = False
                self._attr_is_closing = True
            case _:
                self._attr_is_opening = False
                self._attr_is_closing = False

        if self._entity_info.endpoint.has_attribute(
            None, clusters.Fan.Attributes.PercentCurrent
        ):
            # actual currently operating fan speed, or zero to indicate that the fan is off.
            current_percent = self.get_matter_attribute_value(
                clusters.Fan.Attributes.PercentCurrent
            )
            self._attr_current_percent = (
                100 - floor(current_percent / 100)
                if current_percent is not None
                else None
            )

            LOGGER.debug(
                "Current percent for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_percent,
                self.current_percent,
            )

        # map matter type to HA deviceclass
        device_type: clusters.Fan.Enums.Type = (
            self.get_matter_attribute_value(clusters.Fan.Attributes.Type)
        )
        self._attr_device_class = TYPE_MAP.get(device_type, FanDeviceClass.FAN)

        # This cluster SHALL support the FeatureMap bitmap attribute as defined below.
        '''
        0 SPD MultiSpeed 1-100 speeds
        1 AUT Auto Automatic mode supported for fan speed
        2 RCK Rocking Rocking movement supported
        3 WND Wind Wind emulation supported
        4 STEP Step Step command supported
        5 DIR Airflow Direction Airflow Direction attribute is supported        
        '''
        supported_features = (
            FanEntityFeature.SPD | FanEntityFeature.AUT | FanEntityFeature.RCK | FanEntityFeature.WND | FanEntityFeature.STEP | FanEntityFeature.DIR
        )
        commands = self.get_matter_attribute_value(
            clusters.Fan.Attributes.AcceptedCommandList
        )
        if clusters.Fan.Commands.Setp.command_id in commands:
            supported_features |= FanEntityFeature.SET_PERCENT
        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.FAN,
        entity_description=FanEntityDescription(key="MatterFan", name=None),
        entity_class=MatterFan,
        required_attributes=(
            clusters.Fan.Attributes.OperationalStatus,
            clusters.Fan.Attributes.Type,
        ),
        absent_attributes=(
            clusters.Fan.Attributes.PercentCurrent,
        ),
    ),
]
