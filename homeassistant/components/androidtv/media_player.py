"""Support for functionality to interact with Android / Fire TV devices."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import hashlib
import logging
from typing import Any

from androidtv.constants import APPS, KEYS
from androidtv.setup_async import AndroidTVAsync, FireTVAsync
from androidtvremote2 import AndroidTVRemote, ConnectionClosed, VolumeInfo

from homeassistant.components import persistent_notification
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import AndroidTVADBRuntimeData, AndroidTVConfigEntry, AndroidTVRemoteRuntimeData
from .const import (
    CONF_APP_ICON,
    CONF_APP_NAME,
    CONF_APPS,
    CONF_CONNECTION_TYPE,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_GET_SOURCES,
    CONF_SCREENCAP_INTERVAL,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_GET_SOURCES,
    DEFAULT_SCREENCAP_INTERVAL,
    DEVICE_ANDROIDTV,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
)
from .entity import AndroidTVADBEntity, AndroidTVRemoteEntity, adb_decorator
from .services import ATTR_ADB_RESPONSE, ATTR_HDMI_INPUT, SERVICE_LEARN_SENDEVENT

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Translate from `AndroidTV` / `FireTV` reported state to HA state.
ANDROIDTV_STATES = {
    "off": MediaPlayerState.OFF,
    "idle": MediaPlayerState.IDLE,
    "standby": MediaPlayerState.IDLE,
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndroidTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Android TV media player entity."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE)

    if connection_type == CONNECTION_TYPE_REMOTE:
        # Remote protocol connection
        runtime_data = entry.runtime_data
        assert isinstance(runtime_data, AndroidTVRemoteRuntimeData)
        async_add_entities([AndroidTVRemoteMediaPlayerEntity(runtime_data.api, entry)])
    else:
        # ADB connection
        runtime_data = entry.runtime_data
        assert isinstance(runtime_data, AndroidTVADBRuntimeData)
        device_class = runtime_data.aftv.DEVICE_CLASS
        async_add_entities(
            [
                AndroidTVDevice(entry)
                if device_class == DEVICE_ANDROIDTV
                else FireTVDevice(entry)
            ]
        )


# =============================================================================
# Remote Protocol Media Player Entity
# =============================================================================


class AndroidTVRemoteMediaPlayerEntity(AndroidTVRemoteEntity, MediaPlayerEntity):
    """Android TV Remote Media Player Entity."""

    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(
        self, api: AndroidTVRemote, config_entry: AndroidTVConfigEntry
    ) -> None:
        """Initialize the entity."""
        super().__init__(api, config_entry)

        # This task is needed to create a job that sends a key press
        # sequence that can be canceled if concurrency occurs
        self._channel_set_task: asyncio.Task | None = None

    def _update_current_app(self, current_app: str) -> None:
        """Update current app info."""
        self._attr_app_id = current_app
        self._attr_app_name = (
            self._apps[current_app].get(CONF_APP_NAME, current_app)
            if current_app in self._apps
            else current_app
        )

    def _update_volume_info(self, volume_info: VolumeInfo) -> None:
        """Update volume info."""
        if volume_info.get("max"):
            self._attr_volume_level = volume_info["level"] / volume_info["max"]
            self._attr_is_volume_muted = volume_info["muted"]
        else:
            self._attr_volume_level = None
            self._attr_is_volume_muted = None

    @callback
    def _current_app_updated(self, current_app: str) -> None:
        """Update the state when the current app changes."""
        self._update_current_app(current_app)
        self.async_write_ha_state()

    @callback
    def _volume_info_updated(self, volume_info: VolumeInfo) -> None:
        """Update the state when the volume info changes."""
        self._update_volume_info(volume_info)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self._api.current_app is not None:
            self._update_current_app(self._api.current_app)
        if self._api.volume_info is not None:
            self._update_volume_info(self._api.volume_info)

        self._api.add_current_app_updated_callback(self._current_app_updated)
        self._api.add_volume_info_updated_callback(self._volume_info_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await super().async_will_remove_from_hass()

        self._api.remove_current_app_updated_callback(self._current_app_updated)
        self._api.remove_volume_info_updated_callback(self._volume_info_updated)

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._attr_is_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    async def async_turn_on(self) -> None:
        """Turn the Android TV on."""
        if not self._attr_is_on:
            self._send_key_command("POWER")

    async def async_turn_off(self) -> None:
        """Turn the Android TV off."""
        if self._attr_is_on:
            self._send_key_command("POWER")

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        self._send_key_command("VOLUME_UP")

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        self._send_key_command("VOLUME_DOWN")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute != self.is_volume_muted:
            self._send_key_command("VOLUME_MUTE")

    async def async_media_play(self) -> None:
        """Send play command."""
        self._send_key_command("MEDIA_PLAY")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        self._send_key_command("MEDIA_PAUSE")

    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        self._send_key_command("MEDIA_PLAY_PAUSE")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        self._send_key_command("MEDIA_STOP")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        self._send_key_command("MEDIA_PREVIOUS")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        self._send_key_command("MEDIA_NEXT")

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_type == MediaType.CHANNEL:
            if not media_id.isnumeric():
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_channel",
                    translation_placeholders={"media_id": media_id},
                )
            if self._channel_set_task:
                self._channel_set_task.cancel()
            self._channel_set_task = asyncio.create_task(
                self._send_key_commands(list(media_id))
            )
            await self._channel_set_task
            return

        if media_type in [MediaType.URL, MediaType.APP]:
            self._send_launch_app_command(media_id)
            return

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_media_type",
            translation_placeholders={"media_type": media_type},
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse apps."""
        children = [
            BrowseMedia(
                media_class=MediaClass.APP,
                media_content_type=MediaType.APP,
                media_content_id=app_id,
                title=app.get(CONF_APP_NAME, ""),
                thumbnail=app.get(CONF_APP_ICON, ""),
                can_play=False,
                can_expand=False,
            )
            for app_id, app in self._apps.items()
        ]
        return BrowseMedia(
            title="Applications",
            media_class=MediaClass.DIRECTORY,
            media_content_id="apps",
            media_content_type=MediaType.APPS,
            children_media_class=MediaClass.APP,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _send_key_commands(
        self, key_codes: list[str], delay_secs: float = 0.1
    ) -> None:
        """Send a key press sequence to Android TV."""
        try:
            for key_code in key_codes:
                self._api.send_key_command(key_code)
                await asyncio.sleep(delay_secs)
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_closed"
            ) from exc


# =============================================================================
# ADB Media Player Entities
# =============================================================================


class ADBDevice(AndroidTVADBEntity, MediaPlayerEntity):
    """Representation of an Android or Fire TV device via ADB."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_name = None

    def __init__(self, entry: AndroidTVConfigEntry) -> None:
        """Initialize the Android / Fire TV device."""
        super().__init__(entry)
        self._entry_id = entry.entry_id

        self._media_image: tuple[bytes | None, str | None] = None, None
        self._attr_media_image_hash = None

        self._app_id_to_name: dict[str, str] = {}
        self._app_name_to_id: dict[str, str] = {}
        self._get_sources = DEFAULT_GET_SOURCES
        self._exclude_unnamed_apps = DEFAULT_EXCLUDE_UNNAMED_APPS
        self._screencap_delta: timedelta | None = None
        self._last_screencap: datetime | None = None
        self.turn_on_command: str | None = None
        self.turn_off_command: str | None = None

        # Property attributes
        self._attr_extra_state_attributes = {
            ATTR_ADB_RESPONSE: None,
            ATTR_HDMI_INPUT: None,
        }

        # The number of consecutive failed connect attempts
        self._failed_connect_count = 0

    def _process_config(self) -> None:
        """Load the config options."""
        _LOGGER.debug("Loading configuration options")
        options = self._entry_runtime_data.dev_opt

        apps = options.get(CONF_APPS, {})
        self._app_id_to_name = APPS.copy()
        self._app_id_to_name.update(apps)
        self._app_name_to_id = {
            value: key for key, value in self._app_id_to_name.items() if value
        }

        # Make sure that apps overridden via the `apps` parameter are reflected
        # in `self._app_name_to_id`
        for key, value in apps.items():
            self._app_name_to_id[value] = key

        self._get_sources = options.get(CONF_GET_SOURCES, DEFAULT_GET_SOURCES)
        self._exclude_unnamed_apps = options.get(
            CONF_EXCLUDE_UNNAMED_APPS, DEFAULT_EXCLUDE_UNNAMED_APPS
        )
        screencap_interval: int = options.get(
            CONF_SCREENCAP_INTERVAL, DEFAULT_SCREENCAP_INTERVAL
        )
        if screencap_interval > 0:
            self._screencap_delta = timedelta(minutes=screencap_interval)
        else:
            self._screencap_delta = None
        self.turn_off_command = options.get(CONF_TURN_OFF_COMMAND)
        self.turn_on_command = options.get(CONF_TURN_ON_COMMAND)

    async def async_added_to_hass(self) -> None:
        """Set config parameter when add to hass."""
        await super().async_added_to_hass()
        self._process_config()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_CONFIG_ENTITY}_{self._entry_id}",
                self._process_config,
            )
        )

    @adb_decorator()
    async def _adb_screencap(self) -> bytes | None:
        """Take a screen capture from the device."""
        return await self.aftv.adb_screencap()  # type: ignore[no-any-return]

    async def _async_get_screencap(self, prev_app_id: str | None = None) -> None:
        """Take a screen capture from the device when enabled."""
        if (
            not self._screencap_delta
            or self.state in {MediaPlayerState.OFF, None}
            or not self.available
        ):
            self._media_image = None, None
            self._attr_media_image_hash = None
        else:
            force: bool = prev_app_id is not None
            if force:
                force = prev_app_id != self._attr_app_id
            await self._adb_get_screencap(force)

    async def _adb_get_screencap(self, force: bool = False) -> None:
        """Take a screen capture from the device every configured minutes."""
        time_elapsed = self._screencap_delta is not None and (
            self._last_screencap is None
            or (utcnow() - self._last_screencap) >= self._screencap_delta
        )
        if not (force or time_elapsed):
            return

        self._last_screencap = utcnow()
        if media_data := await self._adb_screencap():
            self._media_image = media_data, "image/png"
            self._attr_media_image_hash = hashlib.sha256(media_data).hexdigest()[:16]
        else:
            self._media_image = None, None
            self._attr_media_image_hash = None

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch current playing image."""
        return self._media_image

    @adb_decorator()
    async def async_media_play(self) -> None:
        """Send play command."""
        await self.aftv.media_play()

    @adb_decorator()
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.aftv.media_pause()

    @adb_decorator()
    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        await self.aftv.media_play_pause()

    @adb_decorator()
    async def async_turn_on(self) -> None:
        """Turn on the device."""
        if self.turn_on_command:
            await self.aftv.adb_shell(self.turn_on_command)
        else:
            await self.aftv.turn_on()

    @adb_decorator()
    async def async_turn_off(self) -> None:
        """Turn off the device."""
        if self.turn_off_command:
            await self.aftv.adb_shell(self.turn_off_command)
        else:
            await self.aftv.turn_off()

    @adb_decorator()
    async def async_media_previous_track(self) -> None:
        """Send previous track command (results in rewind)."""
        await self.aftv.media_previous_track()

    @adb_decorator()
    async def async_media_next_track(self) -> None:
        """Send next track command (results in fast-forward)."""
        await self.aftv.media_next_track()

    @adb_decorator()
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if isinstance(source, str):
            if not source.startswith("!"):
                await self.aftv.launch_app(self._app_name_to_id.get(source, source))
            else:
                source_ = source[1:].lstrip()
                await self.aftv.stop_app(self._app_name_to_id.get(source_, source_))

    @adb_decorator()
    async def adb_command(self, command: str) -> None:
        """Send an ADB command to an Android / Fire TV device."""
        if key := KEYS.get(command):
            await self.aftv.adb_shell(f"input keyevent {key}")
            return

        if command == "GET_PROPERTIES":
            self._attr_extra_state_attributes[ATTR_ADB_RESPONSE] = str(
                await self.aftv.get_properties_dict()
            )
            self.async_write_ha_state()
            return

        try:
            response = await self.aftv.adb_shell(command)
        except UnicodeDecodeError:
            return

        if isinstance(response, str) and response.strip():
            self._attr_extra_state_attributes[ATTR_ADB_RESPONSE] = response.strip()
            self.async_write_ha_state()

        return

    @adb_decorator()
    async def learn_sendevent(self) -> None:
        """Translate a key press on a remote to ADB 'sendevent' commands."""
        output = await self.aftv.learn_sendevent()
        if output:
            self._attr_extra_state_attributes[ATTR_ADB_RESPONSE] = output
            self.async_write_ha_state()

            msg = (
                f"Output from service '{SERVICE_LEARN_SENDEVENT}' from"
                f" {self.entity_id}: '{output}'"
            )
            persistent_notification.async_create(
                self.hass,
                msg,
                title="Android Debug Bridge",
            )
            _LOGGER.debug("%s", msg)

    @adb_decorator()
    async def service_download(self, device_path: str, local_path: str) -> None:
        """Download a file from your Android / Fire TV device."""
        if not self.hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        await self.aftv.adb_pull(local_path, device_path)

    @adb_decorator()
    async def service_upload(self, device_path: str, local_path: str) -> None:
        """Upload a file to an Android / Fire TV device."""
        if not self.hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        await self.aftv.adb_push(local_path, device_path)


class AndroidTVDevice(ADBDevice):
    """Representation of an Android device via ADB."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )
    aftv: AndroidTVAsync

    @adb_decorator(override_available=True)
    async def async_update(self) -> None:
        """Update the device state and, if necessary, re-connect."""
        # Check if device is disconnected.
        if not self._attr_available:
            # Try to connect
            if await self.aftv.adb_connect(log_errors=self._failed_connect_count == 0):
                self._failed_connect_count = 0
                self._attr_available = True
            else:
                self._failed_connect_count += 1

        # If the ADB connection is not intact, don't update.
        if not self.available:
            return

        prev_app_id = self._attr_app_id
        # Get the updated state and attributes.
        (
            state,
            self._attr_app_id,
            running_apps,
            _,
            self._attr_is_volume_muted,
            self._attr_volume_level,
            self._attr_extra_state_attributes[ATTR_HDMI_INPUT],
        ) = await self.aftv.update(self._get_sources)

        self._attr_state = ANDROIDTV_STATES.get(state)
        if self._attr_state is None:
            self._attr_available = False

        if running_apps and self._attr_app_id:
            self._attr_source = self._attr_app_name = self._app_id_to_name.get(
                self._attr_app_id, self._attr_app_id
            )
            sources = [
                self._app_id_to_name.get(
                    app_id, app_id if not self._exclude_unnamed_apps else None
                )
                for app_id in running_apps
            ]
            self._attr_source_list = [source for source in sources if source]
        else:
            self._attr_source_list = None

        await self._async_get_screencap(prev_app_id)

    @adb_decorator()
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.aftv.media_stop()

    @adb_decorator()
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        is_muted = await self.aftv.is_volume_muted()

        # `None` indicates that the muted status could not be determined
        if is_muted is not None and is_muted != mute:
            await self.aftv.mute_volume()

    @adb_decorator()
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self.aftv.set_volume_level(volume)

    @adb_decorator()
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        self._attr_volume_level = await self.aftv.volume_down(self._attr_volume_level)

    @adb_decorator()
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        self._attr_volume_level = await self.aftv.volume_up(self._attr_volume_level)


class FireTVDevice(ADBDevice):
    """Representation of a Fire TV device via ADB."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
    )
    aftv: FireTVAsync

    @adb_decorator(override_available=True)
    async def async_update(self) -> None:
        """Update the device state and, if necessary, re-connect."""
        # Check if device is disconnected.
        if not self._attr_available:
            # Try to connect
            if await self.aftv.adb_connect(log_errors=self._failed_connect_count == 0):
                self._failed_connect_count = 0
                self._attr_available = True
            else:
                self._failed_connect_count += 1

        # If the ADB connection is not intact, don't update.
        if not self.available:
            return

        prev_app_id = self._attr_app_id
        # Get the `state`, `current_app`, `running_apps` and `hdmi_input`.
        (
            state,
            self._attr_app_id,
            running_apps,
            self._attr_extra_state_attributes[ATTR_HDMI_INPUT],
        ) = await self.aftv.update(self._get_sources)

        self._attr_state = ANDROIDTV_STATES.get(state)
        if self._attr_state is None:
            self._attr_available = False

        if running_apps and self._attr_app_id:
            self._attr_source = self._app_id_to_name.get(
                self._attr_app_id, self._attr_app_id
            )
            sources = [
                self._app_id_to_name.get(
                    app_id, app_id if not self._exclude_unnamed_apps else None
                )
                for app_id in running_apps
            ]
            self._attr_source_list = [source for source in sources if source]
        else:
            self._attr_source_list = None

        await self._async_get_screencap(prev_app_id)

    @adb_decorator()
    async def async_media_stop(self) -> None:
        """Send stop (back) command."""
        await self.aftv.back()
