"""The homee cover platform."""

import logging
from typing import Any, cast

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeNodeEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

OPEN_CLOSE_ATTRIBUTES = [
    AttributeType.OPEN_CLOSE,
    AttributeType.SLAT_ROTATION_IMPULSE,
    AttributeType.UP_DOWN,
]
POSITION_ATTRIBUTES = [AttributeType.POSITION, AttributeType.SHUTTER_SLAT_POSITION]


def get_open_close_attribute(node: HomeeNode) -> HomeeAttribute | None:
    """Return the attribute used for opening/closing the cover."""
    # We assume, that no device has UP_DOWN and OPEN_CLOSE, but only one of them.
    if (open_close := node.get_attribute_by_type(AttributeType.UP_DOWN)) is None:
        open_close = node.get_attribute_by_type(AttributeType.OPEN_CLOSE)

    return open_close


def get_cover_features(
    node: HomeeNode, open_close_attribute: HomeeAttribute | None
) -> CoverEntityFeature:
    """Determine the supported cover features of a homee node based on the available attributes."""
    features = CoverEntityFeature(0)

    if (open_close_attribute is not None) and open_close_attribute.editable:
        features |= (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    # Check for up/down position settable.
    attribute = node.get_attribute_by_type(AttributeType.POSITION)
    if attribute is not None:
        if attribute.editable:
            features |= CoverEntityFeature.SET_POSITION

    if node.get_attribute_by_type(AttributeType.SLAT_ROTATION_IMPULSE) is not None:
        features |= CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT

    if node.get_attribute_by_type(AttributeType.SHUTTER_SLAT_POSITION) is not None:
        features |= CoverEntityFeature.SET_TILT_POSITION

    return features


def get_device_class(node: HomeeNode) -> CoverDeviceClass | None:
    """Determine the device class a homee node based on the node profile."""
    COVER_DEVICE_PROFILES = {
        NodeProfile.GARAGE_DOOR_OPERATOR: CoverDeviceClass.GARAGE,
        NodeProfile.ENTRANCE_GATE_OPERATOR: CoverDeviceClass.GATE,
        NodeProfile.SHUTTER_POSITION_SWITCH: CoverDeviceClass.SHUTTER,
    }

    return COVER_DEVICE_PROFILES.get(node.profile)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the homee platform for the cover integration."""

    async_add_devices(
        HomeeCover(node, config_entry)
        for node in config_entry.runtime_data.nodes
        if is_cover_node(node)
    )


def is_cover_node(node: HomeeNode) -> bool:
    """Determine if a node is controllable as a homee cover based on its profile and attributes."""
    return node.profile in [
        NodeProfile.ELECTRIC_MOTOR_METERING_SWITCH,
        NodeProfile.ELECTRIC_MOTOR_METERING_SWITCH_WITHOUT_SLAT_POSITION,
        NodeProfile.ENTRANCE_GATE_OPERATOR,
        NodeProfile.GARAGE_DOOR_OPERATOR,
        NodeProfile.SHUTTER_POSITION_SWITCH,
    ]


class HomeeCover(HomeeNodeEntity, CoverEntity):
    """Representation of a homee cover device."""

    _attr_name = None

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize a homee cover entity."""
        super().__init__(node, entry)
        self._open_close_attribute = get_open_close_attribute(node)
        self._attr_supported_features = get_cover_features(
            node, self._open_close_attribute
        )
        self._attr_device_class = get_device_class(node)
        self._attr_unique_id = (
            f"{self._attr_unique_id}-{self._open_close_attribute.id}"
            if self._open_close_attribute is not None
            else f"{self._attr_unique_id}-0"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the cover's position."""
        # Translate the homee position values to HA's 0-100 scale
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.POSITION)
        ) is not None:
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = attribute.current_value
            position = ((homee_position - homee_min) / (homee_max - homee_min)) * 100

            return int(100 - position)

        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the cover's tilt position."""
        # Translate the homee position values to HA's 0-100 scale
        if (
            attribute := self._node.get_attribute_by_type(
                AttributeType.SHUTTER_SLAT_POSITION
            )
        ) is not None:
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = attribute.current_value
            position = ((homee_position - homee_min) / (homee_max - homee_min)) * 100

            return int(100 - position)

        return None

    @property
    def is_opening(self) -> bool | None:
        """Return the opening status of the cover."""
        if self._open_close_attribute is not None:
            return (
                self._open_close_attribute.get_value() == 3
                if not self._open_close_attribute.is_reversed
                else self._open_close_attribute.get_value() == 4
            )

        return None

    @property
    def is_closing(self) -> bool | None:
        """Return the closing status of the cover."""
        if self._open_close_attribute is not None:
            return (
                self._open_close_attribute.get_value() == 4
                if not self._open_close_attribute.is_reversed
                else self._open_close_attribute.get_value() == 3
            )

        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.POSITION)
        ) is not None:
            return attribute.get_value() == attribute.maximum

        if self._open_close_attribute is not None:
            if not self._open_close_attribute.is_reversed:
                return self._open_close_attribute.get_value() == 1

            return self._open_close_attribute.get_value() == 0

        # If none of the above is present, it might be a slat only cover.
        if (
            attribute := self._node.get_attribute_by_type(
                AttributeType.SHUTTER_SLAT_POSITION
            )
        ) is not None:
            return attribute.get_value() == attribute.minimum

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        assert self._open_close_attribute is not None
        if not self._open_close_attribute.is_reversed:
            await self.async_set_homee_value(self._open_close_attribute, 0)
        else:
            await self.async_set_homee_value(self._open_close_attribute, 1)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        assert self._open_close_attribute is not None
        if not self._open_close_attribute.is_reversed:
            await self.async_set_homee_value(self._open_close_attribute, 1)
        else:
            await self.async_set_homee_value(self._open_close_attribute, 0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if CoverEntityFeature.SET_POSITION in self.supported_features:
            position = 100 - cast(int, kwargs[ATTR_POSITION])

            # Convert position to range of our entity.
            if (
                attribute := self._node.get_attribute_by_type(AttributeType.POSITION)
            ) is not None:
                homee_min = attribute.minimum
                homee_max = attribute.maximum
                homee_position = (position / 100) * (homee_max - homee_min) + homee_min

                await self.async_set_homee_value(attribute, homee_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._open_close_attribute is not None:
            await self.async_set_homee_value(self._open_close_attribute, 2)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if (
            slat_attribute := self._node.get_attribute_by_type(
                AttributeType.SLAT_ROTATION_IMPULSE
            )
        ) is not None:
            if not slat_attribute.is_reversed:
                await self.async_set_homee_value(slat_attribute, 2)
            else:
                await self.async_set_homee_value(slat_attribute, 1)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if (
            slat_attribute := self._node.get_attribute_by_type(
                AttributeType.SLAT_ROTATION_IMPULSE
            )
        ) is not None:
            if not slat_attribute.is_reversed:
                await self.async_set_homee_value(slat_attribute, 1)
            else:
                await self.async_set_homee_value(slat_attribute, 2)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if CoverEntityFeature.SET_TILT_POSITION in self.supported_features:
            position = 100 - cast(int, kwargs[ATTR_TILT_POSITION])

            # Convert position to range of our entity.
            if (
                attribute := self._node.get_attribute_by_type(
                    AttributeType.SHUTTER_SLAT_POSITION
                )
            ) is not None:
                homee_min = attribute.minimum
                homee_max = attribute.maximum
                homee_position = (position / 100) * (homee_max - homee_min) + homee_min

                await self.async_set_homee_value(attribute, homee_position)
