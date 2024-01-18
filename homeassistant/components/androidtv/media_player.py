"""Support for functionality to interact with Android / Fire TV devices."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
import functools
import hashlib
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from androidtv.constants import APPS, KEYS
from androidtv.exceptions import LockNotAcquiredException
from androidtv.setup_async import AndroidTVAsync, FireTVAsync
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_CONNECTIONS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import ADB_PYTHON_EXCEPTIONS, ADB_TCP_EXCEPTIONS, get_androidtv_mac
from .const import (
    ANDROID_DEV,
    ANDROID_DEV_OPT,
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_GET_SOURCES,
    CONF_SCREENCAP,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    DEFAULT_EXCLUDE_UNNAMED_APPS,
    DEFAULT_GET_SOURCES,
    DEFAULT_SCREENCAP,
    DEVICE_ANDROIDTV,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
)

_ADBDeviceT = TypeVar("_ADBDeviceT", bound="ADBDevice")
_R = TypeVar("_R")
_P = ParamSpec("_P")

_LOGGER = logging.getLogger(__name__)

ATTR_ADB_RESPONSE = "adb_response"
ATTR_DEVICE_PATH = "device_path"
ATTR_HDMI_INPUT = "hdmi_input"
ATTR_LOCAL_PATH = "local_path"

MIN_TIME_BETWEEN_SCREENCAPS = timedelta(seconds=60)

SERVICE_ADB_COMMAND = "adb_command"
SERVICE_DOWNLOAD = "download"
SERVICE_LEARN_SENDEVENT = "learn_sendevent"
SERVICE_UPLOAD = "upload"

PREFIX_ANDROIDTV = "Android TV"
PREFIX_FIRETV = "Fire TV"

# Translate from `AndroidTV` / `FireTV` reported state to HA state.
ANDROIDTV_STATES = {
    "off": MediaPlayerState.OFF,
    "idle": MediaPlayerState.IDLE,
    "standby": MediaPlayerState.STANDBY,
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android Debug Bridge entity."""
    aftv: AndroidTVAsync | FireTVAsync = hass.data[DOMAIN][entry.entry_id][ANDROID_DEV]
    device_class = aftv.DEVICE_CLASS
    device_type = (
        PREFIX_ANDROIDTV if device_class == DEVICE_ANDROIDTV else PREFIX_FIRETV
    )
    # CONF_NAME may be present in entry.data for configuration imported from YAML
    device_name: str = entry.data.get(
        CONF_NAME, f"{device_type} {entry.data[CONF_HOST]}"
    )

    device_args = [
        aftv,
        device_name,
        device_type,
        entry.unique_id,
        entry.entry_id,
        hass.data[DOMAIN][entry.entry_id],
    ]

    async_add_entities(
        [
            AndroidTVDevice(*device_args)
            if device_class == DEVICE_ANDROIDTV
            else FireTVDevice(*device_args)
        ]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ADB_COMMAND,
        {vol.Required(ATTR_COMMAND): cv.string},
        "adb_command",
    )
    platform.async_register_entity_service(
        SERVICE_LEARN_SENDEVENT, {}, "learn_sendevent"
    )
    platform.async_register_entity_service(
        SERVICE_DOWNLOAD,
        {
            vol.Required(ATTR_DEVICE_PATH): cv.string,
            vol.Required(ATTR_LOCAL_PATH): cv.string,
        },
        "service_download",
    )
    platform.async_register_entity_service(
        SERVICE_UPLOAD,
        {
            vol.Required(ATTR_DEVICE_PATH): cv.string,
            vol.Required(ATTR_LOCAL_PATH): cv.string,
        },
        "service_upload",
    )


_FuncType = Callable[Concatenate[_ADBDeviceT, _P], Awaitable[_R]]
_ReturnFuncType = Callable[Concatenate[_ADBDeviceT, _P], Coroutine[Any, Any, _R | None]]


def adb_decorator(
    override_available: bool = False,
) -> Callable[[_FuncType[_ADBDeviceT, _P, _R]], _ReturnFuncType[_ADBDeviceT, _P, _R]]:
    """Wrap ADB methods and catch exceptions.

    Allows for overriding the available status of the ADB connection via the
    `override_available` parameter.
    """

    def _adb_decorator(
        func: _FuncType[_ADBDeviceT, _P, _R],
    ) -> _ReturnFuncType[_ADBDeviceT, _P, _R]:
        """Wrap the provided ADB method and catch exceptions."""

        @functools.wraps(func)
        async def _adb_exception_catcher(
            self: _ADBDeviceT, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R | None:
            """Call an ADB-related method and catch exceptions."""
            if not self.available and not override_available:
                return None

            try:
                return await func(self, *args, **kwargs)
            except LockNotAcquiredException:
                # If the ADB lock could not be acquired, skip this command
                _LOGGER.info(
                    (
                        "ADB command %s not executed because the connection is"
                        " currently in use"
                    ),
                    func.__name__,
                )
                return None
            except self.exceptions as err:
                _LOGGER.error(
                    (
                        "Failed to execute an ADB command. ADB connection re-"
                        "establishing attempt in the next update. Error: %s"
                    ),
                    err,
                )
                await self.aftv.adb_close()
                # pylint: disable-next=protected-access
                self._attr_available = False
                return None
            except Exception:
                # An unforeseen exception occurred. Close the ADB connection so that
                # it doesn't happen over and over again, then raise the exception.
                await self.aftv.adb_close()
                # pylint: disable-next=protected-access
                self._attr_available = False
                raise

        return _adb_exception_catcher

    return _adb_decorator


class ADBDevice(MediaPlayerEntity):
    """Representation of an Android or Fire TV device."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        aftv: AndroidTVAsync | FireTVAsync,
        name: str,
        dev_type: str,
        unique_id: str,
        entry_id: str,
        entry_data: dict[str, Any],
    ) -> None:
        """Initialize the Android / Fire TV device."""
        self.aftv = aftv
        self._attr_unique_id = unique_id
        self._entry_id = entry_id
        self._entry_data = entry_data

        self._media_image: tuple[bytes | None, str | None] = None, None
        self._attr_media_image_hash = None

        info = aftv.device_properties
        model = info.get(ATTR_MODEL)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            model=f"{model} ({dev_type})" if model else dev_type,
            name=name,
        )
        if manufacturer := info.get(ATTR_MANUFACTURER):
            self._attr_device_info[ATTR_MANUFACTURER] = manufacturer
        if sw_version := info.get(ATTR_SW_VERSION):
            self._attr_device_info[ATTR_SW_VERSION] = sw_version
        if mac := get_androidtv_mac(info):
            self._attr_device_info[ATTR_CONNECTIONS] = {(CONNECTION_NETWORK_MAC, mac)}

        self._app_id_to_name: dict[str, str] = {}
        self._app_name_to_id: dict[str, str] = {}
        self._get_sources = DEFAULT_GET_SOURCES
        self._exclude_unnamed_apps = DEFAULT_EXCLUDE_UNNAMED_APPS
        self._screencap = DEFAULT_SCREENCAP
        self.turn_on_command: str | None = None
        self.turn_off_command: str | None = None

        # ADB exceptions to catch
        if not aftv.adb_server_ip:
            # Using "adb_shell" (Python ADB implementation)
            self.exceptions = ADB_PYTHON_EXCEPTIONS
        else:
            # Using "pure-python-adb" (communicate with ADB server)
            self.exceptions = ADB_TCP_EXCEPTIONS

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
        options = self._entry_data[ANDROID_DEV_OPT]

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
        self._screencap = options.get(CONF_SCREENCAP, DEFAULT_SCREENCAP)
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
            not self._screencap
            or self.state in {MediaPlayerState.OFF, None}
            or not self.available
        ):
            self._media_image = None, None
            self._attr_media_image_hash = None
        else:
            force: bool = prev_app_id is not None
            if force:
                force = prev_app_id != self._attr_app_id
            await self._adb_get_screencap(no_throttle=force)

    @Throttle(MIN_TIME_BETWEEN_SCREENCAPS)
    async def _adb_get_screencap(self, **kwargs: Any) -> None:
        """Take a screen capture from the device every 60 seconds."""
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
        """Select input source.

        If the source starts with a '!', then it will close the app instead of
        opening it.
        """
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
            _LOGGER.info("%s", msg)

    @adb_decorator()
    async def service_download(self, device_path: str, local_path: str) -> None:
        """Download a file from your Android / Fire TV device to your Home Assistant instance."""
        if not self.hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        await self.aftv.adb_pull(local_path, device_path)

    @adb_decorator()
    async def service_upload(self, device_path: str, local_path: str) -> None:
        """Upload a file from your Home Assistant instance to an Android / Fire TV device."""
        if not self.hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        await self.aftv.adb_push(local_path, device_path)


class AndroidTVDevice(ADBDevice):
    """Representation of an Android device."""

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
    """Representation of a Fire TV device."""

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
