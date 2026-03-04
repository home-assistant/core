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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUPPORT_PTZ_SPEED
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkButtonEntityDescription(
    ButtonEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes button entities for a camera channel."""

    enabled_default: Callable[[Host, int], bool] | None = None
    method: Callable[[Host, int], Any]
    ptz_cmd: str | None = None


@dataclass(frozen=True, kw_only=True)
class ReolinkHostButtonEntityDescription(
    ButtonEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes button entities for the host."""

    method: Callable[[Host], Any]


BUTTON_ENTITIES = (
    ReolinkButtonEntityDescription(
        key="ptz_stop",
        translation_key="ptz_stop",
        enabled_default=lambda api, ch: api.supported(ch, "pan_tilt"),
        supported=lambda api, ch: (
            api.supported(ch, "pan_tilt") or api.supported(ch, "zoom_basic")
        ),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.stop.value),
    ),
    ReolinkButtonEntityDescription(
        key="ptz_left",
        translation_key="ptz_left",
        supported=lambda api, ch: api.supported(ch, "pan"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.left.value),
        ptz_cmd=PtzEnum.left.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_right",
        translation_key="ptz_right",
        supported=lambda api, ch: api.supported(ch, "pan"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.right.value),
        ptz_cmd=PtzEnum.right.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_up",
        translation_key="ptz_up",
        supported=lambda api, ch: api.supported(ch, "tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.up.value),
        ptz_cmd=PtzEnum.up.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_down",
        translation_key="ptz_down",
        supported=lambda api, ch: api.supported(ch, "tilt"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.down.value),
        ptz_cmd=PtzEnum.down.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_zoom_in",
        translation_key="ptz_zoom_in",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "zoom_basic"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.zoomin.value),
        ptz_cmd=PtzEnum.zoomin.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_zoom_out",
        translation_key="ptz_zoom_out",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "zoom_basic"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.zoomout.value),
        ptz_cmd=PtzEnum.zoomout.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_left_up",
        translation_key="ptz_left_up",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "ptz_diagonal"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.leftup.value),
        ptz_cmd=PtzEnum.leftup.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_left_down",
        translation_key="ptz_left_down",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "ptz_diagonal"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.leftdown.value),
        ptz_cmd=PtzEnum.leftdown.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_right_up",
        translation_key="ptz_right_up",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "ptz_diagonal"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.rightup.value),
        ptz_cmd=PtzEnum.rightup.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_right_down",
        translation_key="ptz_right_down",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "ptz_diagonal"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.rightdown.value),
        ptz_cmd=PtzEnum.rightdown.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_auto",
        translation_key="ptz_auto",
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "ptz_auto"),
        method=lambda api, ch: api.set_ptz_command(ch, command=PtzEnum.auto.value),
        ptz_cmd=PtzEnum.auto.value,
    ),
    ReolinkButtonEntityDescription(
        key="ptz_calibrate",
        translation_key="ptz_calibrate",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_callibrate"),
        method=lambda api, ch: api.ptz_callibrate(ch),
    ),
    ReolinkButtonEntityDescription(
        key="guard_go_to",
        translation_key="guard_go_to",
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        method=lambda api, ch: api.set_ptz_guard(ch, command=GuardEnum.goto.value),
    ),
    ReolinkButtonEntityDescription(
        key="guard_set",
        translation_key="guard_set",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        method=lambda api, ch: api.set_ptz_guard(ch, command=GuardEnum.set.value),
    ),
    ReolinkButtonEntityDescription(
        key="reboot",
        always_available=True,
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "reboot"),
        method=lambda api, ch: api.reboot(ch),
    ),
)

HOST_BUTTON_ENTITIES = (
    ReolinkHostButtonEntityDescription(
        key="reboot",
        always_available=True,
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api: api.supported(None, "reboot"),
        method=lambda api: api.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink button entities."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkButtonEntity | ReolinkHostButtonEntity] = [
        ReolinkButtonEntity(reolink_data, channel, entity_description)
        for entity_description in BUTTON_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkHostButtonEntity(reolink_data, entity_description)
        for entity_description in HOST_BUTTON_ENTITIES
        if entity_description.supported(reolink_data.host.api)
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
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

        if entity_description.enabled_default is not None:
            self._attr_entity_registry_enabled_default = (
                entity_description.enabled_default(self._host.api, self._channel)
            )

        if (
            self._host.api.supported(channel, "ptz_speed")
            and entity_description.ptz_cmd is not None
        ):
            self._attr_supported_features = SUPPORT_PTZ_SPEED

    @raise_translated_error
    async def async_press(self) -> None:
        """Execute the button action."""
        await self.entity_description.method(self._host.api, self._channel)

    @raise_translated_error
    async def async_ptz_move(self, speed: int) -> None:
        """PTZ move with speed."""
        await self._host.api.set_ptz_command(
            self._channel, command=self.entity_description.ptz_cmd, speed=speed
        )


class ReolinkHostButtonEntity(ReolinkHostCoordinatorEntity, ButtonEntity):
    """Base button entity class for Reolink hosts."""

    entity_description: ReolinkHostButtonEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostButtonEntityDescription,
    ) -> None:
        """Initialize Reolink button entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

    @raise_translated_error
    async def async_press(self) -> None:
        """Execute the button action."""
        await self.entity_description.method(self._host.api)
