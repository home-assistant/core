"""Component providing support for Reolink button entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import GuardEnum, Host, PtzEnum

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity


@dataclass
class ReolinkButtonEntityDescriptionMixin:
    """Mixin values for Reolink button entities."""

    method: Callable[[Host, int], Any]


@dataclass
class ReolinkButtonEntityDescription(
    ButtonEntityDescription, ReolinkButtonEntityDescriptionMixin
):
    """A class that describes button entities."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True


BUTTON_ENTITIES = (
    ReolinkButtonEntityDescription(
        key="ptz_stop",
        name="PTZ stop",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan_tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.stop.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_left",
        name="PTZ left",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan_tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.left.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_right",
        name="PTZ right",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan_tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.right.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_up",
        name="PTZ up",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan_tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.up.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_down",
        name="PTZ down",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan_tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.down.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_calibrate",
        name="PTZ calibrate",
        icon="mdi:pan",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_callibrate"),
        method=lambda api, ch: api.ptz_callibrate(ch),
    ),
    ReolinkButtonEntityDescription(
        key="guard_go_to",
        name="Guard go to",
        icon="mdi:crosshairs-gps",
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        method=lambda api, ch: api.set_ptz_guard(ch, command=GuardEnum.goto.value),
    ),
    ReolinkButtonEntityDescription(
        key="guard_set",
        name="Guard set current position",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        method=lambda api, ch: api.set_ptz_guard(ch, command=GuardEnum.set.value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink button entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkButtonEntity(reolink_data, channel, entity_description)
        for entity_description in BUTTON_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkButtonEntity(ReolinkChannelCoordinatorEntity, ButtonEntity):
    """Base button entity class for Reolink IP cameras."""

    entity_description: ReolinkButtonEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkButtonEntityDescription,
    ) -> None:
        """Initialize Reolink button entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{entity_description.key}"
        )

    async def async_press(self) -> None:
        """Execute the button action."""
        await self.entity_description.method(self._host.api, self._channel)
