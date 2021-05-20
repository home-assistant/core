"""Support for functionality to interact with Android TV / Fire TV devices."""
from datetime import datetime
import functools
import logging
import os

from adb_shell.auth.keygen import keygen
from adb_shell.exceptions import (
    AdbTimeoutError,
    InvalidChecksumError,
    InvalidCommandError,
    InvalidResponseError,
    TcpTimeoutException,
)
from androidtv import ha_state_detection_rules_validator
from androidtv.adb_manager.adb_manager_sync import ADBPythonSync
from androidtv.constants import APPS, KEYS
from androidtv.exceptions import LockNotAcquiredException
from androidtv.setup_async import setup
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.storage import STORAGE_DIR

ANDROIDTV_DOMAIN = "androidtv"

_LOGGER = logging.getLogger(__name__)

SUPPORT_ANDROIDTV = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

SUPPORT_FIRETV = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_STOP
)

ATTR_DEVICE_PATH = "device_path"
ATTR_LOCAL_PATH = "local_path"

CONF_ADBKEY = "adbkey"
CONF_ADB_SERVER_IP = "adb_server_ip"
CONF_ADB_SERVER_PORT = "adb_server_port"
CONF_APPS = "apps"
CONF_EXCLUDE_UNNAMED_APPS = "exclude_unnamed_apps"
CONF_GET_SOURCES = "get_sources"
CONF_STATE_DETECTION_RULES = "state_detection_rules"
CONF_TURN_ON_COMMAND = "turn_on_command"
CONF_TURN_OFF_COMMAND = "turn_off_command"
CONF_SCREENCAP = "screencap"

DEFAULT_NAME = "Android TV"
DEFAULT_PORT = 5555
DEFAULT_ADB_SERVER_PORT = 5037
DEFAULT_GET_SOURCES = True
DEFAULT_DEVICE_CLASS = "auto"
DEFAULT_SCREENCAP = True

DEVICE_ANDROIDTV = "androidtv"
DEVICE_FIRETV = "firetv"
DEVICE_CLASSES = [DEFAULT_DEVICE_CLASS, DEVICE_ANDROIDTV, DEVICE_FIRETV]

SERVICE_ADB_COMMAND = "adb_command"
SERVICE_DOWNLOAD = "download"
SERVICE_LEARN_SENDEVENT = "learn_sendevent"
SERVICE_UPLOAD = "upload"

SERVICE_ADB_COMMAND_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_ids, vol.Required(ATTR_COMMAND): cv.string}
)

SERVICE_DOWNLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DEVICE_PATH): cv.string,
        vol.Required(ATTR_LOCAL_PATH): cv.string,
    }
)

SERVICE_UPLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_DEVICE_PATH): cv.string,
        vol.Required(ATTR_LOCAL_PATH): cv.string,
    }
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.In(
            DEVICE_CLASSES
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ADBKEY): cv.isfile,
        vol.Optional(CONF_ADB_SERVER_IP): cv.string,
        vol.Optional(CONF_ADB_SERVER_PORT, default=DEFAULT_ADB_SERVER_PORT): cv.port,
        vol.Optional(CONF_GET_SOURCES, default=DEFAULT_GET_SOURCES): cv.boolean,
        vol.Optional(CONF_APPS, default={}): vol.Schema(
            {cv.string: vol.Any(cv.string, None)}
        ),
        vol.Optional(CONF_TURN_ON_COMMAND): cv.string,
        vol.Optional(CONF_TURN_OFF_COMMAND): cv.string,
        vol.Optional(CONF_STATE_DETECTION_RULES, default={}): vol.Schema(
            {cv.string: ha_state_detection_rules_validator(vol.Invalid)}
        ),
        vol.Optional(CONF_EXCLUDE_UNNAMED_APPS, default=False): cv.boolean,
        vol.Optional(CONF_SCREENCAP, default=DEFAULT_SCREENCAP): cv.boolean,
    }
)

# Translate from `AndroidTV` / `FireTV` reported state to HA state.
ANDROIDTV_STATES = {
    "off": STATE_OFF,
    "idle": STATE_IDLE,
    "standby": STATE_STANDBY,
    "playing": STATE_PLAYING,
    "paused": STATE_PAUSED,
}


def setup_androidtv(hass, config):
    """Generate an ADB key (if needed) and load it."""
    adbkey = config.get(CONF_ADBKEY, hass.config.path(STORAGE_DIR, "androidtv_adbkey"))
    if CONF_ADB_SERVER_IP not in config:
        # Use "adb_shell" (Python ADB implementation)
        if not os.path.isfile(adbkey):
            # Generate ADB key files
            keygen(adbkey)

        # Load the ADB key
        signer = ADBPythonSync.load_adbkey(adbkey)
        adb_log = f"using Python ADB implementation with adbkey='{adbkey}'"

    else:
        # Use "pure-python-adb" (communicate with ADB server)
        signer = None
        adb_log = f"using ADB server at {config[CONF_ADB_SERVER_IP]}:{config[CONF_ADB_SERVER_PORT]}"

    return adbkey, signer, adb_log


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Android TV / Fire TV platform."""
    hass.data.setdefault(ANDROIDTV_DOMAIN, {})

    address = f"{config[CONF_HOST]}:{config[CONF_PORT]}"

    if address in hass.data[ANDROIDTV_DOMAIN]:
        _LOGGER.warning("Platform already setup on %s, skipping", address)
        return

    adbkey, signer, adb_log = await hass.async_add_executor_job(
        setup_androidtv, hass, config
    )

    aftv = await setup(
        config[CONF_HOST],
        config[CONF_PORT],
        adbkey,
        config.get(CONF_ADB_SERVER_IP, ""),
        config[CONF_ADB_SERVER_PORT],
        config[CONF_STATE_DETECTION_RULES],
        config[CONF_DEVICE_CLASS],
        10.0,
        signer,
    )

    if not aftv.available:
        # Determine the name that will be used for the device in the log
        if CONF_NAME in config:
            device_name = config[CONF_NAME]
        elif config[CONF_DEVICE_CLASS] == DEVICE_ANDROIDTV:
            device_name = "Android TV device"
        elif config[CONF_DEVICE_CLASS] == DEVICE_FIRETV:
            device_name = "Fire TV device"
        else:
            device_name = "Android TV / Fire TV device"

        _LOGGER.warning(
            "Could not connect to %s at %s %s", device_name, address, adb_log
        )
        raise PlatformNotReady

    async def _async_close(event):
        """Close the ADB socket connection when HA stops."""
        await aftv.adb_close()

    # Close the ADB connection when HA stops
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)

    device_args = [
        aftv,
        config[CONF_NAME],
        config[CONF_APPS],
        config[CONF_GET_SOURCES],
        config.get(CONF_TURN_ON_COMMAND),
        config.get(CONF_TURN_OFF_COMMAND),
        config[CONF_EXCLUDE_UNNAMED_APPS],
        config[CONF_SCREENCAP],
    ]

    if aftv.DEVICE_CLASS == DEVICE_ANDROIDTV:
        device = AndroidTVDevice(*device_args)
        device_name = config.get(CONF_NAME, "Android TV")
    else:
        device = FireTVDevice(*device_args)
        device_name = config.get(CONF_NAME, "Fire TV")

    async_add_entities([device])
    _LOGGER.debug("Setup %s at %s %s", device_name, address, adb_log)
    hass.data[ANDROIDTV_DOMAIN][address] = device

    if hass.services.has_service(ANDROIDTV_DOMAIN, SERVICE_ADB_COMMAND):
        return

    platform = entity_platform.async_get_current_platform()

    async def service_adb_command(service):
        """Dispatch service calls to target entities."""
        cmd = service.data[ATTR_COMMAND]
        entity_id = service.data[ATTR_ENTITY_ID]
        target_devices = [
            dev
            for dev in hass.data[ANDROIDTV_DOMAIN].values()
            if dev.entity_id in entity_id
        ]

        for target_device in target_devices:
            output = await target_device.adb_command(cmd)

            # log the output, if there is any
            if output:
                _LOGGER.info(
                    "Output of command '%s' from '%s': %s",
                    cmd,
                    target_device.entity_id,
                    output,
                )

    hass.services.async_register(
        ANDROIDTV_DOMAIN,
        SERVICE_ADB_COMMAND,
        service_adb_command,
        schema=SERVICE_ADB_COMMAND_SCHEMA,
    )

    platform.async_register_entity_service(
        SERVICE_LEARN_SENDEVENT, {}, "learn_sendevent"
    )

    async def service_download(service):
        """Download a file from your Android TV / Fire TV device to your Home Assistant instance."""
        local_path = service.data[ATTR_LOCAL_PATH]
        if not hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        device_path = service.data[ATTR_DEVICE_PATH]
        entity_id = service.data[ATTR_ENTITY_ID]
        target_device = [
            dev
            for dev in hass.data[ANDROIDTV_DOMAIN].values()
            if dev.entity_id in entity_id
        ][0]

        await target_device.adb_pull(local_path, device_path)

    hass.services.async_register(
        ANDROIDTV_DOMAIN,
        SERVICE_DOWNLOAD,
        service_download,
        schema=SERVICE_DOWNLOAD_SCHEMA,
    )

    async def service_upload(service):
        """Upload a file from your Home Assistant instance to an Android TV / Fire TV device."""
        local_path = service.data[ATTR_LOCAL_PATH]
        if not hass.config.is_allowed_path(local_path):
            _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            return

        device_path = service.data[ATTR_DEVICE_PATH]
        entity_id = service.data[ATTR_ENTITY_ID]
        target_devices = [
            dev
            for dev in hass.data[ANDROIDTV_DOMAIN].values()
            if dev.entity_id in entity_id
        ]

        for target_device in target_devices:
            await target_device.adb_push(local_path, device_path)

    hass.services.async_register(
        ANDROIDTV_DOMAIN, SERVICE_UPLOAD, service_upload, schema=SERVICE_UPLOAD_SCHEMA
    )


def adb_decorator(override_available=False):
    """Wrap ADB methods and catch exceptions.

    Allows for overriding the available status of the ADB connection via the
    `override_available` parameter.
    """

    def _adb_decorator(func):
        """Wrap the provided ADB method and catch exceptions."""

        @functools.wraps(func)
        async def _adb_exception_catcher(self, *args, **kwargs):
            """Call an ADB-related method and catch exceptions."""
            if not self.available and not override_available:
                return None

            try:
                return await func(self, *args, **kwargs)
            except LockNotAcquiredException:
                # If the ADB lock could not be acquired, skip this command
                _LOGGER.info(
                    "ADB command not executed because the connection is currently in use"
                )
                return
            except self.exceptions as err:
                _LOGGER.error(
                    "Failed to execute an ADB command. ADB connection re-"
                    "establishing attempt in the next update. Error: %s",
                    err,
                )
                await self.aftv.adb_close()
                self._available = False
                return None
            except Exception:
                # An unforeseen exception occurred. Close the ADB connection so that
                # it doesn't happen over and over again, then raise the exception.
                await self.aftv.adb_close()
                self._available = False
                raise

        return _adb_exception_catcher

    return _adb_decorator


class ADBDevice(MediaPlayerEntity):
    """Representation of an Android TV or Fire TV device."""

    def __init__(
        self,
        aftv,
        name,
        apps,
        get_sources,
        turn_on_command,
        turn_off_command,
        exclude_unnamed_apps,
        screencap,
    ):
        """Initialize the Android TV / Fire TV device."""
        self.aftv = aftv
        self._name = name
        self._app_id_to_name = APPS.copy()
        self._app_id_to_name.update(apps)
        self._app_name_to_id = {
            value: key for key, value in self._app_id_to_name.items() if value
        }

        # Make sure that apps overridden via the `apps` parameter are reflected
        # in `self._app_name_to_id`
        for key, value in apps.items():
            self._app_name_to_id[value] = key

        self._get_sources = get_sources
        self._keys = KEYS

        self._device_properties = self.aftv.device_properties
        self._unique_id = self._device_properties.get("serialno")

        self.turn_on_command = turn_on_command
        self.turn_off_command = turn_off_command

        self._exclude_unnamed_apps = exclude_unnamed_apps
        self._screencap = screencap

        # ADB exceptions to catch
        if not self.aftv.adb_server_ip:
            # Using "adb_shell" (Python ADB implementation)
            self.exceptions = (
                AdbTimeoutError,
                BrokenPipeError,
                ConnectionResetError,
                ValueError,
                InvalidChecksumError,
                InvalidCommandError,
                InvalidResponseError,
                TcpTimeoutException,
            )
        else:
            # Using "pure-python-adb" (communicate with ADB server)
            self.exceptions = (ConnectionResetError, RuntimeError)

        # Property attributes
        self._adb_response = None
        self._available = True
        self._current_app = None
        self._sources = None
        self._state = None
        self._hdmi_input = None

    @property
    def app_id(self):
        """Return the current app."""
        return self._current_app

    @property
    def app_name(self):
        """Return the friendly name of the current app."""
        return self._app_id_to_name.get(self._current_app, self._current_app)

    @property
    def available(self):
        """Return whether or not the ADB connection is valid."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Provide the last ADB command's response and the device's HDMI input as attributes."""
        return {
            "adb_response": self._adb_response,
            "hdmi_input": self._hdmi_input,
        }

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        return f"{datetime.now().timestamp()}" if self._screencap else None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def source(self):
        """Return the current app."""
        return self._app_id_to_name.get(self._current_app, self._current_app)

    @property
    def source_list(self):
        """Return a list of running apps."""
        return self._sources

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def unique_id(self):
        """Return the device unique id."""
        return self._unique_id

    @adb_decorator()
    async def _adb_screencap(self):
        """Take a screen capture from the device."""
        return await self.aftv.adb_screencap()

    async def async_get_media_image(self):
        """Fetch current playing image."""
        if not self._screencap or self.state in [STATE_OFF, None] or not self.available:
            return None, None

        media_data = await self._adb_screencap()
        if media_data:
            return media_data, "image/png"

        # If an exception occurred and the device is no longer available, write the state
        if not self.available:
            self.async_write_ha_state()

        return None, None

    @adb_decorator()
    async def async_media_play(self):
        """Send play command."""
        await self.aftv.media_play()

    @adb_decorator()
    async def async_media_pause(self):
        """Send pause command."""
        await self.aftv.media_pause()

    @adb_decorator()
    async def async_media_play_pause(self):
        """Send play/pause command."""
        await self.aftv.media_play_pause()

    @adb_decorator()
    async def async_turn_on(self):
        """Turn on the device."""
        if self.turn_on_command:
            await self.aftv.adb_shell(self.turn_on_command)
        else:
            await self.aftv.turn_on()

    @adb_decorator()
    async def async_turn_off(self):
        """Turn off the device."""
        if self.turn_off_command:
            await self.aftv.adb_shell(self.turn_off_command)
        else:
            await self.aftv.turn_off()

    @adb_decorator()
    async def async_media_previous_track(self):
        """Send previous track command (results in rewind)."""
        await self.aftv.media_previous_track()

    @adb_decorator()
    async def async_media_next_track(self):
        """Send next track command (results in fast-forward)."""
        await self.aftv.media_next_track()

    @adb_decorator()
    async def async_select_source(self, source):
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
    async def adb_command(self, cmd):
        """Send an ADB command to an Android TV / Fire TV device."""
        key = self._keys.get(cmd)
        if key:
            await self.aftv.adb_shell(f"input keyevent {key}")
            return

        if cmd == "GET_PROPERTIES":
            self._adb_response = str(await self.aftv.get_properties_dict())
            self.async_write_ha_state()
            return self._adb_response

        try:
            response = await self.aftv.adb_shell(cmd)
        except UnicodeDecodeError:
            return

        if isinstance(response, str) and response.strip():
            self._adb_response = response.strip()
            self.async_write_ha_state()

        return self._adb_response

    @adb_decorator()
    async def learn_sendevent(self):
        """Translate a key press on a remote to ADB 'sendevent' commands."""
        output = await self.aftv.learn_sendevent()
        if output:
            self._adb_response = output
            self.async_write_ha_state()

            msg = f"Output from service '{SERVICE_LEARN_SENDEVENT}' from {self.entity_id}: '{output}'"
            self.hass.components.persistent_notification.async_create(
                msg,
                title="Android TV",
            )
            _LOGGER.info("%s", msg)

    @adb_decorator()
    async def adb_pull(self, local_path, device_path):
        """Download a file from your Android TV / Fire TV device to your Home Assistant instance."""
        await self.aftv.adb_pull(local_path, device_path)

    @adb_decorator()
    async def adb_push(self, local_path, device_path):
        """Upload a file from your Home Assistant instance to an Android TV / Fire TV device."""
        await self.aftv.adb_push(local_path, device_path)


class AndroidTVDevice(ADBDevice):
    """Representation of an Android TV device."""

    def __init__(
        self,
        aftv,
        name,
        apps,
        get_sources,
        turn_on_command,
        turn_off_command,
        exclude_unnamed_apps,
        screencap,
    ):
        """Initialize the Android TV device."""
        super().__init__(
            aftv,
            name,
            apps,
            get_sources,
            turn_on_command,
            turn_off_command,
            exclude_unnamed_apps,
            screencap,
        )

        self._is_volume_muted = None
        self._volume_level = None

    @adb_decorator(override_available=True)
    async def async_update(self):
        """Update the device state and, if necessary, re-connect."""
        # Check if device is disconnected.
        if not self._available:
            # Try to connect
            self._available = await self.aftv.adb_connect(always_log_errors=False)

        # If the ADB connection is not intact, don't update.
        if not self._available:
            return

        # Get the updated state and attributes.
        (
            state,
            self._current_app,
            running_apps,
            _,
            self._is_volume_muted,
            self._volume_level,
            self._hdmi_input,
        ) = await self.aftv.update(self._get_sources)

        self._state = ANDROIDTV_STATES.get(state)
        if self._state is None:
            self._available = False

        if running_apps:
            sources = [
                self._app_id_to_name.get(
                    app_id, app_id if not self._exclude_unnamed_apps else None
                )
                for app_id in running_apps
            ]
            self._sources = [source for source in sources if source]
        else:
            self._sources = None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_volume_muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ANDROIDTV

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume_level

    @adb_decorator()
    async def async_media_stop(self):
        """Send stop command."""
        await self.aftv.media_stop()

    @adb_decorator()
    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self.aftv.mute_volume()

    @adb_decorator()
    async def async_set_volume_level(self, volume):
        """Set the volume level."""
        await self.aftv.set_volume_level(volume)

    @adb_decorator()
    async def async_volume_down(self):
        """Send volume down command."""
        self._volume_level = await self.aftv.volume_down(self._volume_level)

    @adb_decorator()
    async def async_volume_up(self):
        """Send volume up command."""
        self._volume_level = await self.aftv.volume_up(self._volume_level)


class FireTVDevice(ADBDevice):
    """Representation of a Fire TV device."""

    @adb_decorator(override_available=True)
    async def async_update(self):
        """Update the device state and, if necessary, re-connect."""
        # Check if device is disconnected.
        if not self._available:
            # Try to connect
            self._available = await self.aftv.adb_connect(always_log_errors=False)

        # If the ADB connection is not intact, don't update.
        if not self._available:
            return

        # Get the `state`, `current_app`, `running_apps` and `hdmi_input`.
        (
            state,
            self._current_app,
            running_apps,
            self._hdmi_input,
        ) = await self.aftv.update(self._get_sources)

        self._state = ANDROIDTV_STATES.get(state)
        if self._state is None:
            self._available = False

        if running_apps:
            sources = [
                self._app_id_to_name.get(
                    app_id, app_id if not self._exclude_unnamed_apps else None
                )
                for app_id in running_apps
            ]
            self._sources = [source for source in sources if source]
        else:
            self._sources = None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_FIRETV

    @adb_decorator()
    async def async_media_stop(self):
        """Send stop (back) command."""
        await self.aftv.back()
