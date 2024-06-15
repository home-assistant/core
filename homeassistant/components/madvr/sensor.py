"""Sensor entities for the MadVR integration."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadVRCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MadvrIncomingResSensor(coordinator, entry.entry_id),
            MadvrIncomingFrameRateSensor(coordinator, entry.entry_id),
            MadvrIncomingColorSpaceSensor(coordinator, entry.entry_id),
            MadvrIncomingBitDepthSensor(coordinator, entry.entry_id),
            MadvrIncomingColorimetrySensor(coordinator, entry.entry_id),
            MadvrIncomingBlackLevelsSensor(coordinator, entry.entry_id),
            MadvrIncomingAspectRatioSensor(coordinator, entry.entry_id),
            MadvrOutgoingResSensor(coordinator, entry.entry_id),
            MadvrOutgoingFrameRateSensor(coordinator, entry.entry_id),
            MadvrOutgoingColorSpaceSensor(coordinator, entry.entry_id),
            MadvrOutgoingBitDepthSensor(coordinator, entry.entry_id),
            MadvrOutgoingHDRFlagSensor(coordinator, entry.entry_id),
            MadvrOutgoingColorimetrySensor(coordinator, entry.entry_id),
            MadvrOutgoingBlackLevelsSensor(coordinator, entry.entry_id),
            MadvrAspectResSensor(coordinator, entry.entry_id),
            MadvrAspectDecSensor(coordinator, entry.entry_id),
            MadvrAspectIntSensor(coordinator, entry.entry_id),
            MadvrAspectNameSensor(coordinator, entry.entry_id),
            MadvrMaskingResSensor(coordinator, entry.entry_id),
            MadvrMaskingDecSensor(coordinator, entry.entry_id),
            MadvrMaskingIntSensor(coordinator, entry.entry_id),
            MadvrProfileNameSensor(coordinator, entry.entry_id),
            MadvrProfileNumSensor(coordinator, entry.entry_id),
        ]
    )


class MadvrBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for MadVR sensors."""

    def __init__(
        self, coordinator: MadVRCoordinator, name: str, key: str, unique_id: str
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._key = key
        self._attr_unique_id = unique_id

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        val: str = self.coordinator.data.get(self._key, "")
        return val


# ruff: noqa: D107


class MadvrIncomingResSensor(MadvrBaseSensor):
    """Sensor for incoming resolution."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Resolution",
            "incoming_res",
            entry_id,
        )


class MadvrIncomingFrameRateSensor(MadvrBaseSensor):
    """Sensor for incoming frame rate."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Frame Rate",
            "incoming_frame_rate",
            entry_id,
        )


class MadvrIncomingColorSpaceSensor(MadvrBaseSensor):
    """Sensor for incoming color space."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Color Space",
            "incoming_color_space",
            entry_id,
        )


class MadvrIncomingBitDepthSensor(MadvrBaseSensor):
    """Sensor for incoming bit depth."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Bit Depth",
            "incoming_bit_depth",
            entry_id,
        )


class MadvrIncomingColorimetrySensor(MadvrBaseSensor):
    """Sensor for incoming colorimetry."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Colorimetry",
            "incoming_colorimetry",
            entry_id,
        )


class MadvrIncomingBlackLevelsSensor(MadvrBaseSensor):
    """Sensor for incoming black levels."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Black Levels",
            "incoming_black_levels",
            entry_id,
        )


class MadvrIncomingAspectRatioSensor(MadvrBaseSensor):
    """Sensor for incoming aspect ratio."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Incoming Aspect Ratio",
            "incoming_aspect_ratio",
            entry_id,
        )


class MadvrOutgoingResSensor(MadvrBaseSensor):
    """Sensor for outgoing resolution."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Resolution",
            "outgoing_res",
            entry_id,
        )


class MadvrOutgoingFrameRateSensor(MadvrBaseSensor):
    """Sensor for outgoing frame rate."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Frame Rate",
            "outgoing_frame_rate",
            entry_id,
        )


class MadvrOutgoingColorSpaceSensor(MadvrBaseSensor):
    """Sensor for outgoing color space."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Color Space",
            "outgoing_color_space",
            entry_id,
        )


class MadvrOutgoingBitDepthSensor(MadvrBaseSensor):
    """Sensor for outgoing bit depth."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Bit Depth",
            "outgoing_bit_depth",
            entry_id,
        )


class MadvrOutgoingHDRFlagSensor(MadvrBaseSensor):
    """Sensor for outgoing HDR flag."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing HDR Flag",
            "outgoing_hdr_flag",
            entry_id,
        )


class MadvrOutgoingColorimetrySensor(MadvrBaseSensor):
    """Sensor for outgoing colorimetry."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Colorimetry",
            "outgoing_colorimetry",
            entry_id,
        )


class MadvrOutgoingBlackLevelsSensor(MadvrBaseSensor):
    """Sensor for outgoing black levels."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Outgoing Black Levels",
            "outgoing_black_levels",
            entry_id,
        )


class MadvrAspectResSensor(MadvrBaseSensor):
    """Sensor for aspect ratio resolution."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Aspect Ratio Resolution",
            "aspect_res",
            entry_id,
        )


class MadvrAspectDecSensor(MadvrBaseSensor):
    """Sensor for aspect ratio decimal value."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Aspect Ratio Decimal",
            "aspect_dec",
            entry_id,
        )


class MadvrAspectIntSensor(MadvrBaseSensor):
    """Sensor for aspect ratio integer value."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Aspect Ratio Integer",
            "aspect_int",
            entry_id,
        )


class MadvrAspectNameSensor(MadvrBaseSensor):
    """Sensor for aspect ratio name."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Aspect Ratio Name",
            "aspect_name",
            entry_id,
        )


class MadvrMaskingResSensor(MadvrBaseSensor):
    """Sensor for masking resolution."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            f"{coordinator.name} Masking Resolution",
            "masking_res",
            entry_id,
        )


class MadvrMaskingDecSensor(MadvrBaseSensor):
    """Sensor for masking decimal value."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.name} Masking Decimal", "masking_dec", entry_id
        )


class MadvrMaskingIntSensor(MadvrBaseSensor):
    """Sensor for masking integer value."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.name} Masking Integer", "masking_int", entry_id
        )


class MadvrProfileNameSensor(MadvrBaseSensor):
    """Sensor for profile name."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.name} Profile Name", "profile_name", entry_id
        )


class MadvrProfileNumSensor(MadvrBaseSensor):
    """Sensor for profile number."""

    def __init__(self, coordinator: MadVRCoordinator, entry_id: str) -> None:
        super().__init__(
            coordinator, f"{coordinator.name} Profile Number", "profile_num", entry_id
        )
