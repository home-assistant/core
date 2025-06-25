"""Component provides support for the Foscam Switch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity


@dataclass(frozen=True)
class FoscamSwitchEntityDescription(SwitchEntityDescription):
    """A custom entity description that supports a turn_off function."""

    turn_off_fn: Callable[[FoscamGenericSwitch], None] | None = None
    turn_on_fn: Callable[[FoscamGenericSwitch], None] | None = None


def flip_off(switch: FoscamGenericSwitch) -> None:
    """Disable vertical video flipping (flip mode) on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.flip_video, 0)


def mirror_off(switch: FoscamGenericSwitch) -> None:
    """Disable horizontal video mirroring on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.mirror_video, 0)


def ir_off(switch: FoscamGenericSwitch) -> None:
    """Turn off infrared LED lighting on the camera asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.set_infra_led_config, 0
    )
    switch.hass.async_add_executor_job(switch.coordinator.session.open_infra_led)


def wake_up_off(switch: FoscamGenericSwitch) -> None:
    """Put the camera into sleep mode asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.wake_up)


def white_light_off(switch: FoscamGenericSwitch) -> None:
    """Turn off the white light of the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.closeWhiteLight)


def siren_off(switch: FoscamGenericSwitch) -> None:
    """Deactivate the camera's siren alarm asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.setSirenConfig, 0, 100, 0
    )


def volume_off(switch: FoscamGenericSwitch) -> None:
    """Disable audio output (speaker) on the camera asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.setVoiceEnableState, 1
    )


def light_off(switch: FoscamGenericSwitch) -> None:
    """Disable status LED indicator on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setLedEnableState, 1)


def wdr_off(switch: FoscamGenericSwitch) -> None:
    """Disable Wide Dynamic Range (WDR) mode on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setWdrMode, 0)


def hdr_off(switch: FoscamGenericSwitch) -> None:
    """Disable High Dynamic Range (HDR) mode on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setHdrMode, 0)


def flip_on(switch: FoscamGenericSwitch) -> None:
    """Enable vertical video flipping (flip mode) on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.flip_video, 1)


def mirror_on(switch: FoscamGenericSwitch) -> None:
    """Enable horizontal video mirroring on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.mirror_video, 1)


def ir_on(switch: FoscamGenericSwitch) -> None:
    """Turn on infrared LED lighting on the camera asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.set_infra_led_config, 1
    )
    switch.hass.async_add_executor_job(switch.coordinator.session.open_infra_led)


def wake_up_on(switch: FoscamGenericSwitch) -> None:
    """Wake up the camera from sleep mode asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.sleep)


def white_light_on(switch: FoscamGenericSwitch) -> None:
    """Turn on the white light of the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.openWhiteLight)


def siren_on(switch: FoscamGenericSwitch) -> None:
    """Activate the camera's siren alarm asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.setSirenConfig, 1, 100, 0
    )


def volume_on(switch: FoscamGenericSwitch) -> None:
    """Enable audio output (speaker) on the camera asynchronously."""
    switch.hass.async_add_executor_job(
        switch.coordinator.session.setVoiceEnableState, 0
    )


def light_on(switch: FoscamGenericSwitch) -> None:
    """Enable status LED indicator on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setLedEnableState, 0)


def wdr_on(switch: FoscamGenericSwitch) -> None:
    """Enable Wide Dynamic Range (WDR) mode on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setWdrMode, 1)


def hdr_on(switch: FoscamGenericSwitch) -> None:
    """Enable High Dynamic Range (HDR) mode on the camera asynchronously."""
    switch.hass.async_add_executor_job(switch.coordinator.session.setHdrMode, 1)


SWITCH_DESCRIPTIONS: list[FoscamSwitchEntityDescription] = [
    FoscamSwitchEntityDescription(
        key="is_flip",
        translation_key="flip_switch",
        icon="mdi:flip-vertical",
        turn_off_fn=flip_off,
        turn_on_fn=flip_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_mirror",
        translation_key="mirror_switch",
        icon="mdi:mirror",
        turn_off_fn=mirror_off,
        turn_on_fn=mirror_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_openir",
        translation_key="ir_switch",
        icon="mdi:theme-light-dark",
        turn_off_fn=ir_off,
        turn_on_fn=ir_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_asleep",
        translation_key="sleep_switch",
        icon="mdi:sleep",
        turn_off_fn=wake_up_off,
        turn_on_fn=wake_up_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_openwhitelight",
        translation_key="white_light_switch",
        icon="mdi:light-flood-down",
        turn_off_fn=white_light_off,
        turn_on_fn=white_light_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_sirenalarm",
        translation_key="siren_alarm_switch",
        icon="mdi:alarm-note",
        turn_off_fn=siren_off,
        turn_on_fn=siren_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_turnoffvolume",
        translation_key="turn_off_volume_switch",
        icon="mdi:volume-off",
        turn_off_fn=volume_off,
        turn_on_fn=volume_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_turnofflight",
        translation_key="light_status_switch",
        icon="mdi:lightbulb-fluorescent-tube",
        turn_off_fn=light_off,
        turn_on_fn=light_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_openhdr",
        translation_key="hdr_switch",
        icon="mdi:hdr",
        turn_off_fn=hdr_off,
        turn_on_fn=hdr_on,
    ),
    FoscamSwitchEntityDescription(
        key="is_openwdr",
        translation_key="wdr_switch",
        icon="mdi:alpha-w-box",
        turn_off_fn=wdr_off,
        turn_on_fn=wdr_on,
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

    product_info = coordinator.data["product_info"]
    reserve3 = product_info.get("reserve3", "0")

    for description in SWITCH_DESCRIPTIONS:
        if description.key == "is_asleep":
            if not coordinator.data["is_asleep"]["supported"]:
                continue
        elif description.key == "is_OpenHdr":
            if ((1 << 8) & int(reserve3)) != 0:
                continue
        elif description.key == "is_OpenWdr":
            if ((1 << 8) & int(reserve3)) == 0:
                continue

        entities.append(FoscamGenericSwitch(coordinator, description))
    async_add_entities(entities)


class FoscamGenericSwitch(FoscamEntity, SwitchEntity):
    """A generic switch class for Foscam entities."""

    entity_description: FoscamSwitchEntityDescription

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        description: FoscamSwitchEntityDescription,
    ) -> None:
        """Initialize the generic switch."""
        config_entry = coordinator.config_entry
        if config_entry is None:
            raise ValueError("config_entry must not be None")

        super().__init__(coordinator, config_entry_id=config_entry.entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"

        if description.key == "is_asleep":
            self._state = self.coordinator.data["is_asleep"]["status"]
        else:
            self._state = self.coordinator.data.get(self.entity_description.key)

        key = (
            description.translation_key or description.key
        )  # fallback to key if translation_key is None
        self._attr_name = key.replace("_", " ").title()

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(int(self._state or 0))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        if self.entity_description.turn_off_fn:
            self.entity_description.turn_off_fn(self)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the entity."""
        if self.entity_description.turn_on_fn:
            self.entity_description.turn_on_fn(self)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key == "is_asleep":
            self._state = self.coordinator.data["is_asleep"]["status"]
        else:
            self._state = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()
