"""Component providing support for Reolink select entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from reolink_aio.api import (
    DayNightEnum,
    Host,
    SpotlightModeEnum,
    StatusLedEnum,
    TrackMethodEnum,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReolinkSelectEntityDescriptionMixin:
    """Mixin values for Reolink select entities."""

    method: Callable[[Host, int, str], Any]
    get_options: list[str] | Callable[[Host, int], list[str]]


@dataclass
class ReolinkSelectEntityDescription(
    SelectEntityDescription, ReolinkSelectEntityDescriptionMixin
):
    """A class that describes select entities."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True
    value: Callable[[Host, int], str] | None = None


SELECT_ENTITIES = (
    ReolinkSelectEntityDescription(
        key="floodlight_mode",
        translation_key="floodlight_mode",
        icon="mdi:spotlight-beam",
        entity_category=EntityCategory.CONFIG,
        get_options=lambda api, ch: api.whiteled_mode_list(ch),
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        value=lambda api, ch: SpotlightModeEnum(api.whiteled_mode(ch)).name,
        method=lambda api, ch, name: api.set_whiteled(ch, mode=name),
    ),
    ReolinkSelectEntityDescription(
        key="day_night_mode",
        translation_key="day_night_mode",
        icon="mdi:theme-light-dark",
        entity_category=EntityCategory.CONFIG,
        get_options=[mode.name for mode in DayNightEnum],
        supported=lambda api, ch: api.supported(ch, "dayNight"),
        value=lambda api, ch: DayNightEnum(api.daynight_state(ch)).name,
        method=lambda api, ch, name: api.set_daynight(ch, DayNightEnum[name].value),
    ),
    ReolinkSelectEntityDescription(
        key="ptz_preset",
        translation_key="ptz_preset",
        icon="mdi:pan",
        get_options=lambda api, ch: list(api.ptz_presets(ch)),
        supported=lambda api, ch: api.supported(ch, "ptz_presets"),
        method=lambda api, ch, name: api.set_ptz_command(ch, preset=name),
    ),
    ReolinkSelectEntityDescription(
        key="auto_quick_reply_message",
        translation_key="auto_quick_reply_message",
        icon="mdi:message-reply-text-outline",
        get_options=lambda api, ch: list(api.quick_reply_dict(ch).values()),
        supported=lambda api, ch: api.supported(ch, "quick_reply"),
        value=lambda api, ch: api.quick_reply_dict(ch)[api.quick_reply_file(ch)],
        method=lambda api, ch, mess: api.set_quick_reply(
            ch, file_id=[k for k, v in api.quick_reply_dict(ch).items() if v == mess][0]
        ),
    ),
    ReolinkSelectEntityDescription(
        key="auto_track_method",
        translation_key="auto_track_method",
        icon="mdi:target-account",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in TrackMethodEnum],
        supported=lambda api, ch: api.supported(ch, "auto_track_method"),
        value=lambda api, ch: TrackMethodEnum(api.auto_track_method(ch)).name,
        method=lambda api, ch, name: api.set_auto_tracking(ch, method=name),
    ),
    ReolinkSelectEntityDescription(
        key="status_led",
        translation_key="status_led",
        icon="mdi:lightning-bolt-circle",
        entity_category=EntityCategory.CONFIG,
        get_options=[state.name for state in StatusLedEnum],
        supported=lambda api, ch: api.supported(ch, "doorbell_led"),
        value=lambda api, ch: StatusLedEnum(api.doorbell_led(ch)).name,
        method=lambda api, ch, name: api.set_status_led(ch, StatusLedEnum[name].value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink select entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkSelectEntity(reolink_data, channel, entity_description)
        for entity_description in SELECT_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSelectEntity(ReolinkChannelCoordinatorEntity, SelectEntity):
    """Base select entity class for Reolink IP cameras."""

    entity_description: ReolinkSelectEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSelectEntityDescription,
    ) -> None:
        """Initialize Reolink select entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description
        self._log_error = True

        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{entity_description.key}"
        )

        if callable(entity_description.get_options):
            self._attr_options = entity_description.get_options(self._host.api, channel)
        else:
            self._attr_options = entity_description.get_options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if self.entity_description.value is None:
            return None

        try:
            option = self.entity_description.value(self._host.api, self._channel)
        except ValueError:
            if self._log_error:
                _LOGGER.exception("Reolink '%s' has an unknown value", self.name)
                self._log_error = False
            return None

        self._log_error = True
        return option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.method(self._host.api, self._channel, option)
        self.async_write_ha_state()
