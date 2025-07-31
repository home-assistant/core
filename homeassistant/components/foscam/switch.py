"""Component provides support for the Foscam Switch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from libpyfoscamcgi import FoscamCamera

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity


def handle_ir_turn_on(session):
    """Turn on IR LED: sets IR mode to auto (if supported), then turns off the IR LED."""

    session.set_infra_led_config(1)
    session.open_infra_led()


def handle_ir_turn_off(session):
    """Turn off IR LED: sets IR mode to manual (if supported), then turns open the IR LED."""

    session.set_infra_led_config(0)
    session.close_infra_led()


@dataclass(frozen=True, kw_only=True)
class FoscamSwitchEntityDescription(SwitchEntityDescription):
    """A custom entity description that supports a turn_off function."""

    native_value_fn: Callable[..., bool] | None = None
    turn_off_fn: Callable[[FoscamCamera], None]
    turn_on_fn: Callable[[FoscamCamera], None]
    set_ir_config_auto_close: Callable[[FoscamCamera], None] | None = None
    set_ir_config_auto: Callable[[FoscamCamera], None] | None = None


SWITCH_DESCRIPTIONS: list[FoscamSwitchEntityDescription] = [
    FoscamSwitchEntityDescription(
        key="is_flip",
        translation_key="flip_switch",
        native_value_fn=lambda data: data.is_flip,
        turn_off_fn=lambda session: session.flip_video(0),
        turn_on_fn=lambda session: session.flip_video(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_mirror",
        translation_key="mirror_switch",
        native_value_fn=lambda data: data.is_mirror,
        turn_off_fn=lambda session: session.mirror_video(0),
        turn_on_fn=lambda session: session.mirror_video(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_open_ir",
        translation_key="ir_switch",
        native_value_fn=lambda data: data.is_open_ir,
        set_ir_config_auto_close=lambda session: session.set_infra_led_config(0),
        set_ir_config_auto=lambda session: session.set_infra_led_config(1),
        turn_off_fn=handle_ir_turn_off,
        turn_on_fn=handle_ir_turn_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_asleep",
        translation_key="sleep_switch",
        native_value_fn=lambda data: data.is_asleep["status"],
        turn_off_fn=lambda session: session.wake_up(),
        turn_on_fn=lambda session: session.sleep(),
    ),
    FoscamSwitchEntityDescription(
        key="is_open_white_light",
        translation_key="white_light_switch",
        native_value_fn=lambda data: data.is_open_white_light,
        turn_off_fn=lambda session: session.closeWhiteLight(),
        turn_on_fn=lambda session: session.openWhiteLight(),
    ),
    FoscamSwitchEntityDescription(
        key="is_siren_alarm",
        translation_key="siren_alarm_switch",
        native_value_fn=lambda data: data.is_siren_alarm,
        turn_off_fn=lambda session: session.setSirenConfig(0, 100, 0),
        turn_on_fn=lambda session: session.setSirenConfig(1, 100, 0),
    ),
    FoscamSwitchEntityDescription(
        key="is_turn_off_volume",
        translation_key="turn_off_volume_switch",
        native_value_fn=lambda data: data.is_turn_off_volume,
        turn_off_fn=lambda session: session.setVoiceEnableState(1),
        turn_on_fn=lambda session: session.setVoiceEnableState(0),
    ),
    FoscamSwitchEntityDescription(
        key="is_turn_off_light",
        translation_key="turn_off_light_switch",
        native_value_fn=lambda data: data.is_turn_off_light,
        turn_off_fn=lambda session: session.setLedEnableState(0),
        turn_on_fn=lambda session: session.setLedEnableState(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_open_hdr",
        translation_key="hdr_switch",
        native_value_fn=lambda data: data.is_open_hdr,
        turn_off_fn=lambda session: session.setHdrMode(0),
        turn_on_fn=lambda session: session.setHdrMode(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_open_wdr",
        translation_key="wdr_switch",
        native_value_fn=lambda data: data.is_open_wdr,
        turn_off_fn=lambda session: session.setWdrMode(0),
        turn_on_fn=lambda session: session.setWdrMode(1),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up foscam switch from a config entry."""

    coordinator = config_entry.runtime_data
    await coordinator.async_config_entry_first_refresh()

    entities = []

    product_info = coordinator.data.product_info
    reserve3 = product_info.get("reserve3", "0")

    for description in SWITCH_DESCRIPTIONS:
        if description.key == "is_asleep":
            if not coordinator.data.is_asleep["supported"]:
                continue
        elif description.key == "is_open_hdr":
            if ((1 << 8) & int(reserve3)) != 0 or ((1 << 7) & int(reserve3)) == 0:
                continue
        elif description.key == "is_open_wdr":
            if ((1 << 8) & int(reserve3)) == 0:
                continue

        entities.append(FoscamGenericSwitch(coordinator, description))
    async_add_entities(entities)


class FoscamGenericSwitch(FoscamEntity, SwitchEntity):
    """A generic switch class for Foscam entities."""

    _attr_has_entity_name = True
    entity_description: FoscamSwitchEntityDescription

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        description: FoscamSwitchEntityDescription,
    ) -> None:
        """Initialize the generic switch."""
        entry_id = coordinator.config_entry.entry_id
        super().__init__(coordinator, entry_id)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

        if self.entity_description.native_value_fn:
            self._state = self.entity_description.native_value_fn(self.coordinator.data)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._state

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        if self.entity_description.turn_off_fn is not None:
            self.hass.async_add_executor_job(
                self.entity_description.turn_off_fn, self.coordinator.session
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the entity."""
        if self.entity_description.turn_on_fn is not None:
            self.hass.async_add_executor_job(
                self.entity_description.turn_on_fn, self.coordinator.session
            )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.native_value_fn:
            self._state = self.entity_description.native_value_fn(self.coordinator.data)
        self.async_write_ha_state()
