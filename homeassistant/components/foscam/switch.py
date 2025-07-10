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


@dataclass(frozen=True, kw_only=True)
class FoscamSwitchEntityDescription(SwitchEntityDescription):
    """A custom entity description that supports a turn_off function."""

    turn_off_fn: Callable[[FoscamCamera], None]
    turn_on_fn: Callable[[FoscamCamera], None]
    set_ir_config_auto_close: Callable[[FoscamCamera], None] | None = None
    set_ir_config_auto: Callable[[FoscamCamera], None] | None = None


SWITCH_DESCRIPTIONS: list[FoscamSwitchEntityDescription] = [
    FoscamSwitchEntityDescription(
        key="is_flip",
        translation_key="flip_switch",
        icon="mdi:flip-vertical",
        turn_off_fn=lambda session: session.flip_video(0),
        turn_on_fn=lambda session: session.flip_video(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_mirror",
        translation_key="mirror_switch",
        icon="mdi:mirror",
        turn_off_fn=lambda session: session.mirror_video(0),
        turn_on_fn=lambda session: session.mirror_video(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_openir",
        translation_key="ir_switch",
        icon="mdi:theme-light-dark",
        set_ir_config_auto_close=lambda session: session.set_infra_led_config(0),
        set_ir_config_auto=lambda session: session.set_infra_led_config(1),
        turn_off_fn=lambda session: session.close_infra_led(),
        turn_on_fn=lambda session: session.open_infra_led(),
    ),
    FoscamSwitchEntityDescription(
        key="is_asleep",
        translation_key="sleep_switch",
        icon="mdi:sleep",
        turn_off_fn=lambda session: session.wake_up(),
        turn_on_fn=lambda session: session.sleep(),
    ),
    FoscamSwitchEntityDescription(
        key="is_openwhitelight",
        translation_key="white_light_switch",
        icon="mdi:light-flood-down",
        turn_off_fn=lambda session: session.closeWhiteLight(),
        turn_on_fn=lambda session: session.openWhiteLight(),
    ),
    FoscamSwitchEntityDescription(
        key="is_sirenalarm",
        translation_key="siren_alarm_switch",
        icon="mdi:alarm-note",
        turn_off_fn=lambda session: session.setSirenConfig(0, 100, 0),
        turn_on_fn=lambda session: session.setSirenConfig(1, 100, 0),
    ),
    FoscamSwitchEntityDescription(
        key="is_turnoffvolume",
        translation_key="turn_off_volume_switch",
        icon="mdi:volume-off",
        turn_off_fn=lambda session: session.setVoiceEnableState(0),
        turn_on_fn=lambda session: session.setVoiceEnableState(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_turnofflight",
        translation_key="turn_off_light_switch",
        icon="mdi:lightbulb-fluorescent-tube",
        turn_off_fn=lambda session: session.setLedEnableState(1),
        turn_on_fn=lambda session: session.setLedEnableState(0),
    ),
    FoscamSwitchEntityDescription(
        key="is_openhdr",
        translation_key="hdr_switch",
        icon="mdi:hdr",
        turn_off_fn=lambda session: session.setHdrMode(0),
        turn_on_fn=lambda session: session.setHdrMode(1),
    ),
    FoscamSwitchEntityDescription(
        key="is_openwdr",
        translation_key="wdr_switch",
        icon="mdi:alpha-w-box",
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
        elif description.key == "is_openhdr":
            if ((1 << 8) & int(reserve3)) != 0:
                continue
        elif description.key == "is_openwdr":
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

        if description.key == "is_asleep":
            self._state = self.coordinator.data.is_asleep["status"]
        else:
            self._state = getattr(self.coordinator.data, self.entity_description.key)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        # print(self._state)
        return self._state

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        if self.entity_description.key == "is_openir":
            if self.entity_description.set_ir_config_auto_close:
                self.hass.async_add_executor_job(
                    self.entity_description.set_ir_config_auto_close,
                    self.coordinator.session,
                )
        if self.entity_description.turn_off_fn is not None:
            self.hass.async_add_executor_job(
                self.entity_description.turn_off_fn, self.coordinator.session
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the entity."""
        if self.entity_description.key == "is_openir":
            if self.entity_description.set_ir_config_auto:
                self.hass.async_add_executor_job(
                    self.entity_description.set_ir_config_auto, self.coordinator.session
                )
        self.hass.async_add_executor_job(
            self.entity_description.turn_on_fn, self.coordinator.session
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key == "is_asleep":
            self._state = self.coordinator.data.is_asleep["status"]
        else:
            self._state = getattr(self.coordinator.data, self.entity_description.key)
        self.async_write_ha_state()
