"""Support for LG soundbars."""

from __future__ import annotations

from typing import Any

import temescal

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media_player from a config entry created in the integrations UI."""
    async_add_entities(
        [
            LGDevice(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                config_entry.unique_id or config_entry.entry_id,
            )
        ]
    )


class LGDevice(MediaPlayerEntity):
    """Representation of an LG soundbar device."""

    _attr_should_poll = False
    _attr_state = MediaPlayerState.ON
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, host, port, unique_id):
        """Initialize the LG speakers."""
        self._host = host
        self._port = port
        self._attr_unique_id = unique_id

        self._volume = 0
        self._volume_min = 0
        self._volume_max = 0
        self._function = -1
        self._functions = []
        self._equaliser = -1
        self._equalisers = []
        self._mute = 0
        self._rear_volume = 0
        self._rear_volume_min = 0
        self._rear_volume_max = 0
        self._woofer_volume = 0
        self._woofer_volume_min = 0
        self._woofer_volume_max = 0
        self._bass = 0
        self._treble = 0
        self._device = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=host
        )

    async def async_added_to_hass(self) -> None:
        """Register the callback after hass is ready for it."""
        await self.hass.async_add_executor_job(self._connect)

    def _connect(self) -> None:
        """Perform the actual devices setup."""
        self._device = temescal.temescal(
            self._host, port=self._port, callback=self.handle_event
        )
        self._device.get_product_info()
        self._device.get_mac_info()
        self.update()

    def handle_event(self, response):
        """Handle responses from the speakers."""
        data = response.get("data") or {}
        if response["msg"] == "EQ_VIEW_INFO":
            self._update_equalisers(data)
        elif response["msg"] == "SPK_LIST_VIEW_INFO":
            if "i_vol" in data:
                self._volume = data["i_vol"]
            if "i_vol_min" in data:
                self._volume_min = data["i_vol_min"]
            if "i_vol_max" in data:
                self._volume_max = data["i_vol_max"]
            if "b_mute" in data:
                self._mute = data["b_mute"]
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if "b_powerstatus" in data:
                if data["b_powerstatus"]:
                    self._attr_state = MediaPlayerState.ON
                else:
                    self._attr_state = MediaPlayerState.OFF
        elif response["msg"] == "FUNC_VIEW_INFO":
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if "ai_func_list" in data:
                self._functions = data["ai_func_list"]
        elif response["msg"] == "SETTING_VIEW_INFO":
            if "i_rear_min" in data:
                self._rear_volume_min = data["i_rear_min"]
            if "i_rear_max" in data:
                self._rear_volume_max = data["i_rear_max"]
            if "i_rear_level" in data:
                self._rear_volume = data["i_rear_level"]
            if "i_woofer_min" in data:
                self._woofer_volume_min = data["i_woofer_min"]
            if "i_woofer_max" in data:
                self._woofer_volume_max = data["i_woofer_max"]
            if "i_woofer_level" in data:
                self._woofer_volume = data["i_woofer_level"]
            if "i_curr_eq" in data:
                self._equaliser = data["i_curr_eq"]
            if "s_user_name" in data:
                self._attr_name = data["s_user_name"]

        self.schedule_update_ha_state()

    def _update_equalisers(self, data: dict[str, Any]) -> None:
        """Update the equalisers."""
        if "i_bass" in data:
            self._bass = data["i_bass"]
        if "i_treble" in data:
            self._treble = data["i_treble"]
        if "ai_eq_list" in data:
            self._equalisers = data["ai_eq_list"]
        if "i_curr_eq" in data:
            self._equaliser = data["i_curr_eq"]

    def update(self) -> None:
        """Trigger updates from the device."""
        self._device.get_eq()
        self._device.get_info()
        self._device.get_func()
        self._device.get_settings()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume_max != 0:
            return self._volume / self._volume_max
        return 0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        if self._equaliser == -1 or self._equaliser >= len(temescal.equalisers):
            return None
        return temescal.equalisers[self._equaliser]

    @property
    def sound_mode_list(self):
        """Return the available sound modes."""
        return sorted(
            temescal.equalisers[equaliser]
            for equaliser in self._equalisers
            if equaliser < len(temescal.equalisers)
        )

    @property
    def source(self):
        """Return the current input source."""
        if self._function == -1 or self._function >= len(temescal.functions):
            return None
        return temescal.functions[self._function]

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(
            temescal.functions[function]
            for function in self._functions
            if function < len(temescal.functions)
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        volume = volume * self._volume_max
        self._device.set_volume(int(volume))

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self._device.set_mute(mute)

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._device.set_func(temescal.functions.index(source))

    def select_sound_mode(self, sound_mode: str) -> None:
        """Set Sound Mode for Receiver.."""
        self._device.set_eq(temescal.equalisers.index(sound_mode))

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._set_power(True)

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._set_power(False)

    def _set_power(self, status: bool) -> None:
        """Set the media player state."""
        self._device.send_packet(
            {"cmd": "set", "data": {"b_powerkey": status}, "msg": "SPK_LIST_VIEW_INFO"}
        )
