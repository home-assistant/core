"""Component providing support for Reolink number entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity


@dataclass
class ReolinkNumberEntityDescriptionMixin:
    """Mixin values for Reolink number entities."""

    value: Callable[[Host, int], float]
    method: Callable[[Host, int, float], Any]


@dataclass
class ReolinkNumberEntityDescription(
    NumberEntityDescription, ReolinkNumberEntityDescriptionMixin
):
    """A class that describes number entities."""

    mode: NumberMode = NumberMode.AUTO
    supported: Callable[[Host, int], bool] = lambda api, ch: True
    get_min_value: Callable[[Host, int], float] | None = None
    get_max_value: Callable[[Host, int], float] | None = None


NUMBER_ENTITIES = (
    ReolinkNumberEntityDescription(
        key="zoom",
        name="Zoom",
        icon="mdi:magnify",
        mode=NumberMode.SLIDER,
        native_step=1,
        get_min_value=lambda api, ch: api.zoom_range(ch)["zoom"]["pos"]["min"],
        get_max_value=lambda api, ch: api.zoom_range(ch)["zoom"]["pos"]["max"],
        supported=lambda api, ch: api.supported(ch, "zoom"),
        value=lambda api, ch: api.get_zoom(ch),
        method=lambda api, ch, value: api.set_zoom(ch, int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="focus",
        name="Focus",
        icon="mdi:focus-field",
        mode=NumberMode.SLIDER,
        native_step=1,
        get_min_value=lambda api, ch: api.zoom_range(ch)["focus"]["pos"]["min"],
        get_max_value=lambda api, ch: api.zoom_range(ch)["focus"]["pos"]["max"],
        supported=lambda api, ch: api.supported(ch, "focus"),
        value=lambda api, ch: api.get_focus(ch),
        method=lambda api, ch, value: api.set_focus(ch, int(value)),
    ),
    # "Floodlight turn on brightness" controls the brightness of the floodlight when
    # it is turned on internally by the camera (see "select.floodlight_mode" entity)
    # or when using the "light.floodlight" entity.
    ReolinkNumberEntityDescription(
        key="floodlight_brightness",
        name="Floodlight turn on brightness",
        icon="mdi:spotlight-beam",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=1,
        native_max_value=100,
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        value=lambda api, ch: api.whiteled_brightness(ch),
        method=lambda api, ch, value: api.set_whiteled(ch, brightness=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="volume",
        name="Volume",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: api.supported(ch, "volume"),
        value=lambda api, ch: api.volume(ch),
        method=lambda api, ch, value: api.set_volume(ch, volume=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="guard_return_time",
        name="Guard return time",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=10,
        native_max_value=300,
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        value=lambda api, ch: api.ptz_guard_time(ch),
        method=lambda api, ch, value: api.set_ptz_guard(ch, time=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="motion_sensitivity",
        name="Motion sensitivity",
        icon="mdi:motion-sensor",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=1,
        native_max_value=50,
        supported=lambda api, ch: api.supported(ch, "md_sensitivity"),
        value=lambda api, ch: api.md_sensitivity(ch),
        method=lambda api, ch, value: api.set_md_sensitivity(ch, int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="ai_face_sensititvity",
        name="AI face sensitivity",
        icon="mdi:face-recognition",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.ai_supported(ch, "face")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "face"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "face"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_person_sensititvity",
        name="AI person sensitivity",
        icon="mdi:account",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.ai_supported(ch, "people")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "people"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "people"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_vehicle_sensititvity",
        name="AI vehicle sensitivity",
        icon="mdi:car",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.ai_supported(ch, "vehicle")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "vehicle"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "vehicle"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_sensititvity",
        name="AI pet sensitivity",
        icon="mdi:dog-side",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.ai_supported(ch, "dog_cat")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_face_delay",
        name="AI face delay",
        icon="mdi:face-recognition",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.ai_supported(ch, "face")
        ),
        value=lambda api, ch: api.ai_delay(ch, "face"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "face"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_person_delay",
        name="AI person delay",
        icon="mdi:account",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.ai_supported(ch, "people")
        ),
        value=lambda api, ch: api.ai_delay(ch, "people"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "people"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_vehicle_delay",
        name="AI vehicle delay",
        icon="mdi:car",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.ai_supported(ch, "vehicle")
        ),
        value=lambda api, ch: api.ai_delay(ch, "vehicle"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "vehicle"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_delay",
        name="AI pet delay",
        icon="mdi:dog-side",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.ai_supported(ch, "dog_cat")
        ),
        value=lambda api, ch: api.ai_delay(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="auto_quick_reply_time",
        name="Auto quick reply time",
        icon="mdi:message-reply-text-outline",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=1,
        native_max_value=60,
        supported=lambda api, ch: api.supported(ch, "quick_reply"),
        value=lambda api, ch: api.quick_reply_time(ch),
        method=lambda api, ch, value: api.set_quick_reply(ch, time=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="auto_track_limit_left",
        name="Auto track limit left",
        icon="mdi:angle-acute",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=-1,
        native_max_value=2700,
        supported=lambda api, ch: api.supported(ch, "auto_track_limit"),
        value=lambda api, ch: api.auto_track_limit_left(ch),
        method=lambda api, ch, value: api.set_auto_track_limit(ch, left=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="auto_track_limit_right",
        name="Auto track limit right",
        icon="mdi:angle-acute",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=-1,
        native_max_value=2700,
        supported=lambda api, ch: api.supported(ch, "auto_track_limit"),
        value=lambda api, ch: api.auto_track_limit_right(ch),
        method=lambda api, ch, value: api.set_auto_track_limit(ch, right=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="auto_track_disappear_time",
        name="Auto track disappear time",
        icon="mdi:target-account",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=1,
        native_max_value=60,
        supported=lambda api, ch: api.supported(ch, "auto_track_disappear_time"),
        value=lambda api, ch: api.auto_track_disappear_time(ch),
        method=lambda api, ch, value: api.set_auto_tracking(
            ch, disappear_time=int(value)
        ),
    ),
    ReolinkNumberEntityDescription(
        key="auto_track_stop_time",
        name="Auto track stop time",
        icon="mdi:target-account",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=1,
        native_max_value=60,
        supported=lambda api, ch: api.supported(ch, "auto_track_stop_time"),
        value=lambda api, ch: api.auto_track_stop_time(ch),
        method=lambda api, ch, value: api.set_auto_tracking(ch, stop_time=int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink number entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkNumberEntity(reolink_data, channel, entity_description)
        for entity_description in NUMBER_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkNumberEntity(ReolinkChannelCoordinatorEntity, NumberEntity):
    """Base number entity class for Reolink IP cameras."""

    entity_description: ReolinkNumberEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkNumberEntityDescription,
    ) -> None:
        """Initialize Reolink number entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        if entity_description.get_min_value is not None:
            self._attr_native_min_value = entity_description.get_min_value(
                self._host.api, channel
            )
        if entity_description.get_max_value is not None:
            self._attr_native_max_value = entity_description.get_max_value(
                self._host.api, channel
            )
        self._attr_mode = entity_description.mode
        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{entity_description.key}"
        )

    @property
    def native_value(self) -> float:
        """State of the number entity."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.method(self._host.api, self._channel, value)
        self.async_write_ha_state()
