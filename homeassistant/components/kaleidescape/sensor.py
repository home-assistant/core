"""Sensor platform for Kaleidescape integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory

from .const import DOMAIN as KALEIDESCAPE_DOMAIN
from .entity import KaleidescapeEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from kaleidescape import Device as KaleidescapeDevice

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required descriptor keys."""

    value_fn: Callable[[KaleidescapeDevice], StateType]


@dataclass
class KaleidescapeSensorEntityDescription(
    SensorEntityDescription, BaseEntityDescriptionMixin
):
    """Describes Kaleidescape sensor entity."""


SENSOR_TYPES: tuple[KaleidescapeSensorEntityDescription, ...] = (
    KaleidescapeSensorEntityDescription(
        key="media_location",
        name="Media Location",
        icon="mdi:monitor",
        value_fn=lambda device: device.automation.movie_location,
    ),
    KaleidescapeSensorEntityDescription(
        key="play_status",
        name="Play Status",
        icon="mdi:monitor",
        value_fn=lambda device: device.movie.play_status,
    ),
    KaleidescapeSensorEntityDescription(
        key="play_speed",
        name="Play Speed",
        icon="mdi:monitor",
        value_fn=lambda device: device.movie.play_speed,
    ),
    KaleidescapeSensorEntityDescription(
        key="video_mode",
        name="Video Mode",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.video_mode,
    ),
    KaleidescapeSensorEntityDescription(
        key="video_color_eotf",
        name="Video Color EOTF",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.video_color_eotf,
    ),
    KaleidescapeSensorEntityDescription(
        key="video_color_space",
        name="Video Color Space",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.video_color_space,
    ),
    KaleidescapeSensorEntityDescription(
        key="video_color_depth",
        name="Video Color Depth",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.video_color_depth,
    ),
    KaleidescapeSensorEntityDescription(
        key="video_color_sampling",
        name="Video Color Sampling",
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.video_color_sampling,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_ratio",
        name="Screen Mask Ratio",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.screen_mask_ratio,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_top_trim_rel",
        name="Screen Mask Top Trim Rel",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.automation.screen_mask_top_trim_rel / 10.0,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_bottom_trim_rel",
        name="Screen Mask Bottom Trim Rel",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.automation.screen_mask_bottom_trim_rel / 10.0,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_conservative_ratio",
        name="Screen Mask Conservative Ratio",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.screen_mask_conservative_ratio,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_top_mask_abs",
        name="Screen Mask Top Mask Abs",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.automation.screen_mask_top_mask_abs / 10.0,
    ),
    KaleidescapeSensorEntityDescription(
        key="screen_mask_bottom_mask_abs",
        name="Screen Mask Bottom Mask Abs",
        icon="mdi:monitor-screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.automation.screen_mask_bottom_mask_abs / 10.0,
    ),
    KaleidescapeSensorEntityDescription(
        key="cinemascape_mask",
        name="Cinemascape Mask",
        icon="mdi:monitor-star",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.cinemascape_mask,
    ),
    KaleidescapeSensorEntityDescription(
        key="cinemascape_mode",
        name="Cinemascape Mode",
        icon="mdi:monitor-star",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.automation.cinemascape_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    device: KaleidescapeDevice = hass.data[KALEIDESCAPE_DOMAIN][entry.entry_id]
    async_add_entities(
        KaleidescapeSensor(device, description) for description in SENSOR_TYPES
    )


class KaleidescapeSensor(KaleidescapeEntity, SensorEntity):
    """Representation of a Kaleidescape sensor."""

    entity_description: KaleidescapeSensorEntityDescription

    def __init__(
        self,
        device: KaleidescapeDevice,
        entity_description: KaleidescapeSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self._attr_name = f"{self._attr_name} {entity_description.name}"

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self._device)
