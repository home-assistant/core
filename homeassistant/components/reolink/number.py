"""Component providing support for Reolink number entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Chime, Host
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkChimeCoordinatorEntity,
)


@dataclass(frozen=True, kw_only=True)
class ReolinkNumberEntityDescription(
    NumberEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes number entities."""

    get_max_value: Callable[[Host, int], float] | None = None
    get_min_value: Callable[[Host, int], float] | None = None
    method: Callable[[Host, int, float], Any]
    mode: NumberMode = NumberMode.AUTO
    value: Callable[[Host, int], float | None]


@dataclass(frozen=True, kw_only=True)
class ReolinkChimeNumberEntityDescription(
    NumberEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes number entities for a chime."""

    method: Callable[[Chime, float], Any]
    mode: NumberMode = NumberMode.AUTO
    value: Callable[[Chime], float | None]


NUMBER_ENTITIES = (
    ReolinkNumberEntityDescription(
        key="zoom",
        cmd_key="GetZoomFocus",
        translation_key="zoom",
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
        cmd_key="GetZoomFocus",
        translation_key="focus",
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
        cmd_key="GetWhiteLed",
        translation_key="floodlight_brightness",
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
        cmd_key="GetAudioCfg",
        translation_key="volume",
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
        cmd_key="GetPtzGuard",
        translation_key="guard_return_time",
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
        cmd_key="GetMdAlarm",
        translation_key="motion_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=1,
        native_max_value=50,
        supported=lambda api, ch: api.supported(ch, "md_sensitivity"),
        value=lambda api, ch: api.md_sensitivity(ch),
        method=lambda api, ch, value: api.set_md_sensitivity(ch, int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="pir_sensitivity",
        cmd_key="GetPirInfo",
        translation_key="pir_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=1,
        native_max_value=100,
        supported=lambda api, ch: api.supported(ch, "PIR"),
        value=lambda api, ch: api.pir_sensitivity(ch),
        method=lambda api, ch, value: api.set_pir(ch, sensitivity=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="ai_face_sensititvity",
        cmd_key="GetAiAlarm",
        translation_key="ai_face_sensitivity",
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
        cmd_key="GetAiAlarm",
        translation_key="ai_person_sensitivity",
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
        cmd_key="GetAiAlarm",
        translation_key="ai_vehicle_sensitivity",
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
        key="ai_package_sensititvity",
        cmd_key="GetAiAlarm",
        translation_key="ai_package_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.ai_supported(ch, "package")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "package"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "package"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_sensititvity",
        cmd_key="GetAiAlarm",
        translation_key="ai_pet_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity")
            and api.ai_supported(ch, "dog_cat")
            and not api.supported(ch, "ai_animal")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_sensititvity",
        cmd_key="GetAiAlarm",
        translation_key="ai_animal_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: (
            api.supported(ch, "ai_sensitivity") and api.supported(ch, "ai_animal")
        ),
        value=lambda api, ch: api.ai_sensitivity(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_sensitivity(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_face_delay",
        cmd_key="GetAiAlarm",
        translation_key="ai_face_delay",
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
        cmd_key="GetAiAlarm",
        translation_key="ai_person_delay",
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
        cmd_key="GetAiAlarm",
        translation_key="ai_vehicle_delay",
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
        key="ai_package_delay",
        cmd_key="GetAiAlarm",
        translation_key="ai_package_delay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.ai_supported(ch, "package")
        ),
        value=lambda api, ch: api.ai_delay(ch, "package"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "package"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_delay",
        cmd_key="GetAiAlarm",
        translation_key="ai_pet_delay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay")
            and api.ai_supported(ch, "dog_cat")
            and not api.supported(ch, "ai_animal")
        ),
        value=lambda api, ch: api.ai_delay(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="ai_pet_delay",
        cmd_key="GetAiAlarm",
        translation_key="ai_animal_delay",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=8,
        supported=lambda api, ch: (
            api.supported(ch, "ai_delay") and api.supported(ch, "ai_animal")
        ),
        value=lambda api, ch: api.ai_delay(ch, "dog_cat"),
        method=lambda api, ch, value: api.set_ai_delay(ch, int(value), "dog_cat"),
    ),
    ReolinkNumberEntityDescription(
        key="auto_quick_reply_time",
        cmd_key="GetAutoReply",
        translation_key="auto_quick_reply_time",
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
        cmd_key="GetPtzTraceSection",
        translation_key="auto_track_limit_left",
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
        cmd_key="GetPtzTraceSection",
        translation_key="auto_track_limit_right",
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
        cmd_key="GetAiCfg",
        translation_key="auto_track_disappear_time",
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
        cmd_key="GetAiCfg",
        translation_key="auto_track_stop_time",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=1,
        native_max_value=60,
        supported=lambda api, ch: api.supported(ch, "auto_track_stop_time"),
        value=lambda api, ch: api.auto_track_stop_time(ch),
        method=lambda api, ch, value: api.set_auto_tracking(ch, stop_time=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="day_night_switch_threshold",
        cmd_key="GetIsp",
        translation_key="day_night_switch_threshold",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        supported=lambda api, ch: api.supported(ch, "dayNightThreshold"),
        value=lambda api, ch: api.daynight_threshold(ch),
        method=lambda api, ch, value: api.set_daynight_threshold(ch, int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="image_brightness",
        cmd_key="GetImage",
        translation_key="image_brightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        supported=lambda api, ch: api.supported(ch, "isp_bright"),
        value=lambda api, ch: api.image_brightness(ch),
        method=lambda api, ch, value: api.set_image(ch, bright=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="image_contrast",
        cmd_key="GetImage",
        translation_key="image_contrast",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        supported=lambda api, ch: api.supported(ch, "isp_contrast"),
        value=lambda api, ch: api.image_contrast(ch),
        method=lambda api, ch, value: api.set_image(ch, contrast=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="image_saturation",
        cmd_key="GetImage",
        translation_key="image_saturation",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        supported=lambda api, ch: api.supported(ch, "isp_satruation"),
        value=lambda api, ch: api.image_saturation(ch),
        method=lambda api, ch, value: api.set_image(ch, saturation=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="image_sharpness",
        cmd_key="GetImage",
        translation_key="image_sharpness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        supported=lambda api, ch: api.supported(ch, "isp_sharpen"),
        value=lambda api, ch: api.image_sharpness(ch),
        method=lambda api, ch, value: api.set_image(ch, sharpen=int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="image_hue",
        cmd_key="GetImage",
        translation_key="image_hue",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        supported=lambda api, ch: api.supported(ch, "isp_hue"),
        value=lambda api, ch: api.image_hue(ch),
        method=lambda api, ch, value: api.set_image(ch, hue=int(value)),
    ),
)

CHIME_NUMBER_ENTITIES = (
    ReolinkChimeNumberEntityDescription(
        key="volume",
        cmd_key="DingDongOpt",
        translation_key="volume",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=4,
        value=lambda chime: chime.volume,
        method=lambda chime, value: chime.set_option(volume=int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink number entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ReolinkNumberEntity | ReolinkChimeNumberEntity] = [
        ReolinkNumberEntity(reolink_data, channel, entity_description)
        for entity_description in NUMBER_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkChimeNumberEntity(reolink_data, chime, entity_description)
        for entity_description in CHIME_NUMBER_ENTITIES
        for chime in reolink_data.host.api.chime_list
    )
    async_add_entities(entities)


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
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

        if entity_description.get_min_value is not None:
            self._attr_native_min_value = entity_description.get_min_value(
                self._host.api, channel
            )
        if entity_description.get_max_value is not None:
            self._attr_native_max_value = entity_description.get_max_value(
                self._host.api, channel
            )
        self._attr_mode = entity_description.mode

    @property
    def native_value(self) -> float | None:
        """State of the number entity."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.entity_description.method(self._host.api, self._channel, value)
        except InvalidParameterError as err:
            raise ServiceValidationError(err) from err
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()


class ReolinkChimeNumberEntity(ReolinkChimeCoordinatorEntity, NumberEntity):
    """Base number entity class for Reolink IP cameras."""

    entity_description: ReolinkChimeNumberEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        chime: Chime,
        entity_description: ReolinkChimeNumberEntityDescription,
    ) -> None:
        """Initialize Reolink chime number entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, chime)

        self._attr_mode = entity_description.mode

    @property
    def native_value(self) -> float | None:
        """State of the number entity."""
        return self.entity_description.value(self._chime)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.entity_description.method(self._chime, value)
        except InvalidParameterError as err:
            raise ServiceValidationError(err) from err
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()
