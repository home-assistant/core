"""The homee cover platform."""

import logging
from typing import Any, cast

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeNode

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeNodeEntity

_LOGGER = logging.getLogger(__name__)

OPEN_CLOSE_ATTRIBUTES = [
    AttributeType.OPEN_CLOSE,
    AttributeType.SLAT_ROTATION_IMPULSE,
    AttributeType.UP_DOWN,
]
POSITION_ATTRIBUTES = [AttributeType.POSITION, AttributeType.SHUTTER_SLAT_POSITION]


def get_cover_features(
    node: HomeeNodeEntity,
) -> tuple[CoverEntityFeature, AttributeType]:
    """Determine the supported cover features of a homee node based on the available attributes."""
    features = CoverEntityFeature(0)
    open_close = None

    # We assume, that no device has UP_DOWN and OPEN_CLOSE, but only one of them.
    if node.has_attribute(AttributeType.UP_DOWN) or node.has_attribute(
        AttributeType.OPEN_CLOSE
    ):
        if node.has_attribute(AttributeType.UP_DOWN):
            open_close = AttributeType.UP_DOWN
        else:
            open_close = AttributeType.OPEN_CLOSE

        if node.get_attribute(open_close).editable:
            features |= (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )

    # Check for up/down position settable.
    if node.has_attribute(AttributeType.POSITION):
        if node.get_attribute(AttributeType.POSITION).editable:
            features |= CoverEntityFeature.SET_POSITION

    if node.has_attribute(AttributeType.SLAT_ROTATION_IMPULSE):
        features |= CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT

    if node.has_attribute(AttributeType.SHUTTER_SLAT_POSITION):
        features |= CoverEntityFeature.SET_TILT_POSITION

    return features, open_close


def get_device_class(node: HomeeNode) -> CoverDeviceClass | None:
    """Determine the device class a homee node based on the node profile."""
    COVER_DEVICE_PROFILES = {
        NodeProfile.GARAGE_DOOR_OPERATOR: CoverDeviceClass.GARAGE,
        NodeProfile.SHUTTER_POSITION_SWITCH: CoverDeviceClass.SHUTTER,
    }

    return COVER_DEVICE_PROFILES.get(node.profile, None)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Add the homee platform for the cover integration."""

    devices: list[HomeeCover] = []
    nodes = config_entry.runtime_data.nodes
    devices.extend(
        HomeeCover(node, config_entry) for node in nodes if is_cover_node(node)
    )

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
        NodeProfile.GARAGE_DOOR_OPERATOR,
        NodeProfile.SHUTTER_POSITION_SWITCH,
    ]


class HomeeCover(HomeeNodeEntity, CoverEntity):
    """Representation of a homee cover device."""

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize a homee cover entity."""
        super().__init__(node, entry)
        self._attr_supported_features, self._open_close_attribute = get_cover_features(
            self
        )
        self._device_class = get_device_class(node)
        self._attr_name = None
        self._attr_unique_id = f"{entry.runtime_data.settings.uid}-{self._node.id}-{self.get_attribute(self._open_close_attribute).id}"

    @property
    def current_cover_position(self) -> int | None:
        """Return the cover's position."""
        # Translate the homee position values to HA's 0-100 scale
        if self.has_attribute(AttributeType.POSITION):
            attribute = self.get_attribute(AttributeType.POSITION)
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = attribute.current_value
            position = ((homee_position - homee_min) / (homee_max - homee_min)) * 100

            return 100 - position

        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the cover's tilt position."""
        # Translate the homee position values to HA's 0-100 scale
        if self.has_attribute(AttributeType.SHUTTER_SLAT_POSITION):
            attribute = self.get_attribute(AttributeType.SHUTTER_SLAT_POSITION)
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = attribute.current_value
            position = ((homee_position - homee_min) / (homee_max - homee_min)) * 100

            return 100 - position

        return None

    @property
    def is_opening(self) -> bool | None:
        """Return the opening status of the cover."""
        if self._open_close_attribute is not None:
            return (
                self.attribute(self._open_close_attribute) == 3
                if not self.is_reversed(self._open_close_attribute)
                else self.attribute(self._open_close_attribute) == 4
            )

        return None

    @property
    def is_closing(self) -> bool | None:
        """Return the closing status of the cover."""
        if self._open_close_attribute is not None:
            return (
                self.attribute(self._open_close_attribute) == 4
                if not self.is_reversed(self._open_close_attribute)
                else self.attribute(self._open_close_attribute) == 3
            )

        return None

    @property
    def is_closed(self) -> bool | None:
        """Return the state of the cover."""
        if self.has_attribute(AttributeType.POSITION):
            return (
                self.attribute(AttributeType.POSITION)
                == self.get_attribute(AttributeType.POSITION).maximum
            )

        if self._open_close_attribute is not None:
            if not self.is_reversed(self._open_close_attribute):
                return self.attribute(self._open_close_attribute) == 1

            return self.attribute(self._open_close_attribute) == 0

        # If none of the above is present, it might be a slat only cover.
        if self.has_attribute(AttributeType.SHUTTER_SLAT_POSITION):
            return (
                self.attribute(AttributeType.SHUTTER_SLAT_POSITION)
                == self.get_attribute(AttributeType.SHUTTER_SLAT_POSITION).minimum
            )

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if not self.is_reversed(self._open_close_attribute):
            await self.async_set_value(self._open_close_attribute, 0)
        else:
            await self.async_set_value(self._open_close_attribute, 1)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if not self.is_reversed(self._open_close_attribute):
            await self.async_set_value(self._open_close_attribute, 1)
        else:
            await self.async_set_value(self._open_close_attribute, 0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if CoverEntityFeature.SET_POSITION in self.supported_features:
            position = 100 - cast(int, kwargs[ATTR_POSITION])

            # Convert position to range of our entity.
            attribute = self.get_attribute(AttributeType.POSITION)
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = (position / 100) * (homee_max - homee_min) + homee_min

            await self.async_set_value(AttributeType.POSITION, homee_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.async_set_value(self._open_close_attribute, 2)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if not self.is_reversed(AttributeType.SLAT_ROTATION_IMPULSE):
            await self.async_set_value(AttributeType.SLAT_ROTATION_IMPULSE, 2)
        else:
            await self.async_set_value(AttributeType.SLAT_ROTATION_IMPULSE, 1)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if not self.is_reversed(AttributeType.SLAT_ROTATION_IMPULSE):
            await self.async_set_value(AttributeType.SLAT_ROTATION_IMPULSE, 1)
        else:
            await self.async_set_value(AttributeType.SLAT_ROTATION_IMPULSE, 2)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if CoverEntityFeature.SET_TILT_POSITION in self.supported_features:
            position = 100 - cast(int, kwargs[ATTR_TILT_POSITION])

            # Convert position to range of our entity.
            attribute = self.get_attribute(AttributeType.SHUTTER_SLAT_POSITION)
            homee_min = attribute.minimum
            homee_max = attribute.maximum
            homee_position = (position / 100) * (homee_max - homee_min) + homee_min

            await self.async_set_value(
                AttributeType.SHUTTER_SLAT_POSITION, homee_position
            )
