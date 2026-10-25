"""Matter cover."""

from dataclasses import dataclass
from enum import IntEnum
from math import floor
from typing import Any, override

from chip.clusters import Objects as clusters

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema

# The MASK used for extracting bits 0 to 1 of the byte.
OPERATIONAL_STATUS_MASK = 0b11

# Cover state is derived from both the operational status and the current
# position, which some devices report as separate attribute updates shortly
# after each other (e.g. stopped before the final position). Debounce state
# writes to avoid writing intermittent states.
STATE_WRITE_DEBOUNCE_COOLDOWN = 0.1

# map Matter window cover types to HA device class
TYPE_MAP = {
    clusters.WindowCovering.Enums.Type.kRollerShade: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShade2Motor: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShadeExterior: CoverDeviceClass.SHADE,
    clusters.WindowCovering.Enums.Type.kRollerShadeExterior2Motor: (
        CoverDeviceClass.SHADE
    ),
    clusters.WindowCovering.Enums.Type.kAwning: CoverDeviceClass.AWNING,
    clusters.WindowCovering.Enums.Type.kDrapery: CoverDeviceClass.CURTAIN,
    clusters.WindowCovering.Enums.Type.kTiltBlindTiltOnly: CoverDeviceClass.BLIND,
    clusters.WindowCovering.Enums.Type.kTiltBlindLiftAndTilt: CoverDeviceClass.BLIND,
}


class OperationalStatus(IntEnum):
    """Ongoing operations enumeration for coverings per Matter spec."""

    COVERING_IS_CURRENTLY_NOT_MOVING = 0b00
    COVERING_IS_CURRENTLY_OPENING = 0b01
    COVERING_IS_CURRENTLY_CLOSING = 0b10
    RESERVED = 0b11


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter Cover from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.COVER, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterCoverEntityDescription(CoverEntityDescription, MatterEntityDescription):
    """Describe Matter Cover entities."""


class MatterCover(MatterEntity, CoverEntity):
    """Representation of a Matter Cover."""

    _write_state_debounce_cooldown = STATE_WRITE_DEBOUNCE_COOLDOWN
    entity_description: MatterCoverEntityDescription

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return true if cover is closed, None if no position."""
        if not self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
        ):
            return None

        return (
            self.current_cover_position == 0
            if self.current_cover_position is not None
            else None
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.send_device_command(clusters.WindowCovering.Commands.StopMotion())

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.UpOrOpen())

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_device_command(clusters.WindowCovering.Commands.DownOrClose())

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self.send_device_command(
            # value needs to be inverted and is sent in 100ths
            clusters.WindowCovering.Commands.GoToLiftPercentage((100 - position) * 100)
        )

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt to a specific position."""
        position = kwargs[ATTR_TILT_POSITION]
        await self.send_device_command(
            # value needs to be inverted and is sent in 100ths
            clusters.WindowCovering.Commands.GoToTiltPercentage((100 - position) * 100)
        )

    @callback
    def _positions_at_target(self) -> bool | None:
        """Return whether all supported positions match their target position.

        Returns None if the positions cannot be compared, e.g. the device is
        not position aware or a position is (still) unknown. The axes to
        compare are taken from the FeatureMap: lift and tilt are independently
        position aware (PA_LF conformance `[LF]`, PA_TL conformance `[TL]`),
        so a supported axis which is not position aware, or lacks its position
        attributes, makes the covering not comparable as a whole, while
        position attributes of an unsupported axis (reported as null by e.g.
        the Shelly 2PM Gen4) are ignored.
        """
        feature_map = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.FeatureMap
        )
        features = clusters.WindowCovering.Bitmaps.Feature
        at_target: bool | None = None
        for feature, position_aware_feature, current_attribute, target_attribute in (
            (
                features.kLift,
                features.kPositionAwareLift,
                clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
                clusters.WindowCovering.Attributes.TargetPositionLiftPercent100ths,
            ),
            (
                features.kTilt,
                features.kPositionAwareTilt,
                clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
                clusters.WindowCovering.Attributes.TargetPositionTiltPercent100ths,
            ),
        ):
            if not feature_map & feature:
                continue
            if not feature_map & position_aware_feature:
                return None
            if not self._entity_info.endpoint.has_attribute(
                None, current_attribute
            ) or not self._entity_info.endpoint.has_attribute(None, target_attribute):
                return None
            current_position = self.get_matter_attribute_value(current_attribute)
            target_position = self.get_matter_attribute_value(target_attribute)
            if current_position is None or target_position is None:
                return None
            if current_position != target_position:
                return False
            at_target = True
        return at_target

    @callback
    @override
    def _update_from_device(self) -> None:
        """Update from device."""
        operational_status = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.OperationalStatus
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

        # Some bridges (e.g. Rademacher SmartHome Box) report current = target
        # with a moving status that never clears. Being at the target only ever
        # clears the moving state; at movement start the debounce hides a status
        # report arriving before the target update.
        if (at_target := self._positions_at_target()) is None:
            detection = "positions not comparable"
        else:
            detection = f"positions at target: {at_target}"
        if at_target and (self._attr_is_opening or self._attr_is_closing):
            LOGGER.debug(
                "Ignoring moving operational status for %s, position(s) match target position(s)",
                self.entity_id,
            )
            self._attr_is_opening = False
            self._attr_is_closing = False
        LOGGER.debug(
            "Movement state for %s: opening=%s closing=%s (%s)",
            self.entity_id,
            self._attr_is_opening,
            self._attr_is_closing,
            detection,
        )

        if self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
        ):
            # current position is inverted in matter (100 is closed, 0 is open)
            current_cover_position = self.get_matter_attribute_value(
                clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths
            )
            self._attr_current_cover_position = (
                100 - floor(current_cover_position / 100)
                if current_cover_position is not None
                else None
            )

            LOGGER.debug(
                "Current position for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_cover_position,
                self.current_cover_position,
            )

        has_tilt_position_attribute = self._entity_info.endpoint.has_attribute(
            None, clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths
        )
        if has_tilt_position_attribute:
            # current tilt position is inverted in matter (100 is closed, 0 is open)
            current_cover_tilt_position = self.get_matter_attribute_value(
                clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths
            )
            self._attr_current_cover_tilt_position = (
                100 - floor(current_cover_tilt_position / 100)
                if current_cover_tilt_position is not None
                else None
            )

            LOGGER.debug(
                "Current tilt position for %s - raw: %s - corrected: %s",
                self.entity_id,
                current_cover_tilt_position,
                self.current_cover_tilt_position,
            )

        # map matter type to HA deviceclass
        device_type: clusters.WindowCovering.Enums.Type = (
            self.get_matter_attribute_value(clusters.WindowCovering.Attributes.Type)
        )
        self._attr_device_class = TYPE_MAP.get(device_type, CoverDeviceClass.AWNING)

        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        commands = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.AcceptedCommandList
        )
        feature_map = self.get_matter_attribute_value(
            clusters.WindowCovering.Attributes.FeatureMap
        )
        if clusters.WindowCovering.Commands.GoToLiftPercentage.command_id in commands:
            supported_features |= CoverEntityFeature.SET_POSITION
        # Some devices report GoToTiltPercentage in AcceptedCommandList even
        # without tilt support, so also require the FeatureMap Tilt bit.
        if (
            clusters.WindowCovering.Commands.GoToTiltPercentage.command_id in commands
            and feature_map & clusters.WindowCovering.Bitmaps.Feature.kTilt
        ):
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCover",
            name=None,
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareLift", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
        ),
        optional_attributes=(
            clusters.WindowCovering.Attributes.TargetPositionLiftPercent100ths,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareTilt", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
        ),
        optional_attributes=(
            clusters.WindowCovering.Attributes.TargetPositionTiltPercent100ths,
        ),
        absent_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.COVER,
        entity_description=MatterCoverEntityDescription(
            key="MatterCoverPositionAwareLiftAndTilt", name=None
        ),
        entity_class=MatterCover,
        required_attributes=(
            clusters.WindowCovering.Attributes.OperationalStatus,
            clusters.WindowCovering.Attributes.Type,
            clusters.WindowCovering.Attributes.CurrentPositionLiftPercent100ths,
        ),
        # tilt is optional, not required: some devices (e.g. Shelly 2PM Gen4)
        # report it as present but null instead of omitting it when tilt is
        # disabled, which would otherwise fail schema matching
        optional_attributes=(
            clusters.WindowCovering.Attributes.CurrentPositionTiltPercent100ths,
            clusters.WindowCovering.Attributes.TargetPositionLiftPercent100ths,
            clusters.WindowCovering.Attributes.TargetPositionTiltPercent100ths,
        ),
    ),
]
