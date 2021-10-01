"""Support for interface with an Samsung TV."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from wakeonlan import send_magic_packet

from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.samsungtv.bridge import (
    SamsungTVLegacyBridge,
    SamsungTVWSBridge,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_component
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)

KEY_PRESS_TIMEOUT = 1.2
SOURCES = {"TV": "KEY_TV", "HDMI": "KEY_HDMI"}

SUPPORT_SAMSUNGTV = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

# Since the TV will take a few seconds to go to sleep
# and actually be seen as off, we need to wait just a bit
# more than the next scan interval
SCAN_INTERVAL_PLUS_OFF_TIME = entity_component.DEFAULT_SCAN_INTERVAL + timedelta(
    seconds=5
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Samsung TV from a config entry."""
    bridge = hass.data[DOMAIN][entry.entry_id]

    host = entry.data[CONF_HOST]
    on_script = None
    data = hass.data[DOMAIN]
    if turn_on_action := data.get(host, {}).get(CONF_ON_ACTION):
        on_script = Script(
            hass, turn_on_action, entry.data.get(CONF_NAME, DEFAULT_NAME), DOMAIN
        )

    async_add_entities([SamsungTVDevice(bridge, entry, on_script)], True)


class SamsungTVDevice(MediaPlayerEntity):
    """Representation of a Samsung TV."""

    def __init__(
        self,
        bridge: SamsungTVLegacyBridge | SamsungTVWSBridge,
        config_entry: ConfigEntry,
        on_script: Script | None,
    ) -> None:
        """Initialize the Samsung device."""
        self._config_entry = config_entry
        self._host: str | None = config_entry.data[CONF_HOST]
        self._mac: str | None = config_entry.data.get(CONF_MAC)
        self._manufacturer: str | None = config_entry.data.get(CONF_MANUFACTURER)
        self._model: str | None = config_entry.data.get(CONF_MODEL)
        self._name: str | None = config_entry.data.get(CONF_NAME)
        self._on_script = on_script
        self._uuid = config_entry.unique_id
        # Assume that the TV is not muted
        self._muted: bool = False
        # Assume that the TV is in Play mode
        self._playing: bool = True
        self._state: str | None = None
        # Mark the end of a shutdown command (need to wait 15 seconds before
        # sending the next command to avoid turning the TV back ON).
        self._end_of_power_off: datetime | None = None
        self._bridge = bridge
        self._auth_failed = False
        self._bridge.register_reauth_callback(self.access_denied)

    def access_denied(self) -> None:
        """Access denied callback."""
        LOGGER.debug("Access denied in getting remote object")
        self._auth_failed = True
        self.hass.create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_REAUTH,
                    "entry_id": self._config_entry.entry_id,
                },
                data=self._config_entry.data,
            )
        )

    def update(self) -> None:
        """Update state of device."""
        if self._auth_failed:
            return
        if self._power_off_in_progress():
            self._state = STATE_OFF
        else:
            self._state = STATE_ON if self._bridge.is_on() else STATE_OFF

    def send_key(self, key: str) -> None:
        """Send a key to the tv and handles exceptions."""
        if self._power_off_in_progress() and key != "KEY_POWEROFF":
            LOGGER.info("TV is powering off, not sending command: %s", key)
            return
        self._bridge.send_key(key)

    def _power_off_in_progress(self) -> bool:
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the device."""
        return self._uuid

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self._state

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._auth_failed:
            return False
        return (
            self._state == STATE_ON
            or self._on_script is not None
            or self._mac is not None
            or self._power_off_in_progress()
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        info: DeviceInfo = {
            "name": self.name,
            "manufacturer": self._manufacturer,
            "model": self._model,
        }
        if self.unique_id:
            info["identifiers"] = {(DOMAIN, self.unique_id)}
        if self._mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, self._mac)}
        return info

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source_list(self) -> list:
        """List of available input sources."""
        return list(SOURCES)

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        if self._on_script or self._mac:
            return SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
        return SUPPORT_SAMSUNGTV

    @property
    def device_class(self) -> str:
        """Set the device class to TV."""
        return DEVICE_CLASS_TV

    def turn_off(self) -> None:
        """Turn off media player."""
        self._end_of_power_off = dt_util.utcnow() + SCAN_INTERVAL_PLUS_OFF_TIME

        self.send_key("KEY_POWEROFF")
        # Force closing of remote session to provide instant UI feedback
        self._bridge.close_remote()

    def volume_up(self) -> None:
        """Volume up the media player."""
        self.send_key("KEY_VOLUP")

    def volume_down(self) -> None:
        """Volume down media player."""
        self.send_key("KEY_VOLDOWN")

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self.send_key("KEY_MUTE")

    def media_play_pause(self) -> None:
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self) -> None:
        """Send play command."""
        self._playing = True
        self.send_key("KEY_PLAY")

    def media_pause(self) -> None:
        """Send media pause command to media player."""
        self._playing = False
        self.send_key("KEY_PAUSE")

    def media_next_track(self) -> None:
        """Send next track command."""
        self.send_key("KEY_CHUP")

    def media_previous_track(self) -> None:
        """Send the previous track command."""
        self.send_key("KEY_CHDOWN")

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Support changing a channel."""
        if media_type != MEDIA_TYPE_CHANNEL:
            LOGGER.error("Unsupported media type")
            return

        # media_id should only be a channel number
        try:
            cv.positive_int(media_id)
        except vol.Invalid:
            LOGGER.error("Media ID must be positive integer")
            return

        for digit in media_id:
            await self.hass.async_add_executor_job(self.send_key, f"KEY_{digit}")
            await asyncio.sleep(KEY_PRESS_TIMEOUT, self.hass.loop)
        await self.hass.async_add_executor_job(self.send_key, "KEY_ENTER")

    def _wake_on_lan(self) -> None:
        """Wake the device via wake on lan."""
        send_magic_packet(self._mac, ip_address=self._host)
        # If the ip address changed since we last saw the device
        # broadcast a packet as well
        send_magic_packet(self._mac)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if self._on_script:
            await self._on_script.async_run(context=self._context)
        elif self._mac:
            await self.hass.async_add_executor_job(self._wake_on_lan)

    def select_source(self, source: str) -> None:
        """Select input source."""
        if source not in SOURCES:
            LOGGER.error("Unsupported source")
            return

        self.send_key(SOURCES[source])
