"""Component providing support for Reolink button entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import GuardEnum, Host, PtzEnum

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity, ReolinkHostCoordinatorEntity


@dataclass
class ReolinkButtonEntityDescriptionMixin:
    """Mixin values for Reolink button entities for a camera channel."""

    method: Callable[[Host, int], Any]


@dataclass
class ReolinkButtonEntityDescription(
    ButtonEntityDescription, ReolinkButtonEntityDescriptionMixin
):
    """A class that describes button entities for a camera channel."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True
    enabled_default: Callable[[Host, int], bool] | None = None


@dataclass
class ReolinkHostButtonEntityDescriptionMixin:
    """Mixin values for Reolink button entities for the host."""

    method: Callable[[Host], Any]


@dataclass
class ReolinkHostButtonEntityDescription(
    ButtonEntityDescription, ReolinkHostButtonEntityDescriptionMixin
):
    """A class that describes button entities for the host."""

    supported: Callable[[Host], bool] = lambda api: True


BUTTON_ENTITIES = (
    ReolinkButtonEntityDescription(
        key="ptz_stop",
        name="PTZ stop",
        icon="mdi:pan",
        enabled_default=lambda api, ch: api.supported(ch, "pan_tilt"),
        supported=lambda api, ch: api.supported(ch, "pan_tilt") or api.supported(ch, "zoom_basic"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.stop.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_left",
        name="PTZ left",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.left.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_right",
        name="PTZ right",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "pan"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.right.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_up",
        name="PTZ up",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.up.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_down",
        name="PTZ down",
        icon="mdi:pan",
        supported=lambda api, ch: api.supported(ch, "tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.down.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_zoom_in",
        name="PTZ zoom in",
        icon="mdi:magnify",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "zoom_basic"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.zoomin.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_zoom_out",
        name="PTZ zoom out",
        icon="mdi:magnify",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "zoom_basic"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.zoomout.value),
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

HOST_BUTTON_ENTITIES = (
    ReolinkHostButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api: api.supported(None, "reboot"),
        method=lambda api: api.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink button entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ReolinkButtonEntity | ReolinkHostButtonEntity] = [
        ReolinkButtonEntity(reolink_data, channel, entity_description)
        for entity_description in BUTTON_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        [
            ReolinkHostButtonEntity(reolink_data, entity_description)
            for entity_description in HOST_BUTTON_ENTITIES
            if entity_description.supported(reolink_data.host.api)
        ]
    )
    async_add_entities(entities)


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
        if entity_description.enabled_default is not None:
            self._attr_entity_registry_enabled_default = entity_description.enabled_default(self._host.api, self._channel)

    async def async_press(self) -> None:
        """Execute the button action."""
        await self.entity_description.method(self._host.api, self._channel)


class ReolinkHostButtonEntity(ReolinkHostCoordinatorEntity, ButtonEntity):
    """Base button entity class for Reolink IP cameras."""

    entity_description: ReolinkHostButtonEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostButtonEntityDescription,
    ) -> None:
        """Initialize Reolink button entity."""
        super().__init__(reolink_data)
        self.entity_description = entity_description

        self._attr_unique_id = f"{self._host.unique_id}_{entity_description.key}"

    async def async_press(self) -> None:
        """Execute the button action."""
        await self.entity_description.method(self._host.api)
