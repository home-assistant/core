"""Support for Amcrest IP cameras."""
import asyncio
from datetime import timedelta
from functools import partial
import logging

from amcrest import AmcrestError
from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import (
    CAMERA_SERVICE_SCHEMA,
    SUPPORT_ON_OFF,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream,
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CAMERA_WEB_SESSION_TIMEOUT,
    CAMERAS,
    COMM_TIMEOUT,
    DATA_AMCREST,
    DEVICES,
    SERVICE_UPDATE,
    SNAPSHOT_TIMEOUT,
)
from .helpers import log_update_error, service_signal

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=15)

STREAM_SOURCE_LIST = ["snapshot", "mjpeg", "rtsp"]

_SRV_EN_REC = "enable_recording"
_SRV_DS_REC = "disable_recording"
_SRV_EN_AUD = "enable_audio"
_SRV_DS_AUD = "disable_audio"
_SRV_EN_MOT_REC = "enable_motion_recording"
_SRV_DS_MOT_REC = "disable_motion_recording"
_SRV_GOTO = "goto_preset"
_SRV_CBW = "set_color_bw"
_SRV_TOUR_ON = "start_tour"
_SRV_TOUR_OFF = "stop_tour"

_SRV_PTZ_CTRL = "ptz_control"
_ATTR_PTZ_TT = "travel_time"
_ATTR_PTZ_MOV = "movement"
_MOV = [
    "zoom_out",
    "zoom_in",
    "right",
    "left",
    "up",
    "down",
    "right_down",
    "right_up",
    "left_down",
    "left_up",
]
_ZOOM_ACTIONS = ["ZoomWide", "ZoomTele"]
_MOVE_1_ACTIONS = ["Right", "Left", "Up", "Down"]
_MOVE_2_ACTIONS = ["RightDown", "RightUp", "LeftDown", "LeftUp"]
_ACTION = _ZOOM_ACTIONS + _MOVE_1_ACTIONS + _MOVE_2_ACTIONS

_DEFAULT_TT = 0.2

_ATTR_PRESET = "preset"
_ATTR_COLOR_BW = "color_bw"

_CBW_COLOR = "color"
_CBW_AUTO = "auto"
_CBW_BW = "bw"
_CBW = [_CBW_COLOR, _CBW_AUTO, _CBW_BW]

_SRV_GOTO_SCHEMA = CAMERA_SERVICE_SCHEMA.extend(
    {vol.Required(_ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1))}
)
_SRV_CBW_SCHEMA = CAMERA_SERVICE_SCHEMA.extend(
    {vol.Required(_ATTR_COLOR_BW): vol.In(_CBW)}
)
_SRV_PTZ_SCHEMA = CAMERA_SERVICE_SCHEMA.extend(
    {
        vol.Required(_ATTR_PTZ_MOV): vol.In(_MOV),
        vol.Optional(_ATTR_PTZ_TT, default=_DEFAULT_TT): cv.small_float,
    }
)

CAMERA_SERVICES = {
    _SRV_EN_REC: (CAMERA_SERVICE_SCHEMA, "async_enable_recording", ()),
    _SRV_DS_REC: (CAMERA_SERVICE_SCHEMA, "async_disable_recording", ()),
    _SRV_EN_AUD: (CAMERA_SERVICE_SCHEMA, "async_enable_audio", ()),
    _SRV_DS_AUD: (CAMERA_SERVICE_SCHEMA, "async_disable_audio", ()),
    _SRV_EN_MOT_REC: (CAMERA_SERVICE_SCHEMA, "async_enable_motion_recording", ()),
    _SRV_DS_MOT_REC: (CAMERA_SERVICE_SCHEMA, "async_disable_motion_recording", ()),
    _SRV_GOTO: (_SRV_GOTO_SCHEMA, "async_goto_preset", (_ATTR_PRESET,)),
    _SRV_CBW: (_SRV_CBW_SCHEMA, "async_set_color_bw", (_ATTR_COLOR_BW,)),
    _SRV_TOUR_ON: (CAMERA_SERVICE_SCHEMA, "async_start_tour", ()),
    _SRV_TOUR_OFF: (CAMERA_SERVICE_SCHEMA, "async_stop_tour", ()),
    _SRV_PTZ_CTRL: (
        _SRV_PTZ_SCHEMA,
        "async_ptz_control",
        (_ATTR_PTZ_MOV, _ATTR_PTZ_TT),
    ),
}

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities([AmcrestCam(name, device, hass.data[DATA_FFMPEG])], True)


class CannotSnapshot(Exception):
    """Conditions are not valid for taking a snapshot."""


class AmcrestCommandFailed(Exception):
    """Amcrest camera command did not work."""


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, name, device, ffmpeg):
        """Initialize an Amcrest camera."""
        super().__init__()
        self._name = name
        self._api = device.api
        self._ffmpeg = ffmpeg
        self._ffmpeg_arguments = device.ffmpeg_arguments
        self._stream_source = device.stream_source
        self._resolution = device.resolution
        self._token = self._auth = device.authentication
        self._control_light = device.control_light
        self._is_recording = False
        self._motion_detection_enabled = None
        self._brand = None
        self._model = None
        self._audio_enabled = None
        self._motion_recording_enabled = None
        self._color_bw = None
        self._rtsp_url = None
        self._snapshot_task = None
        self._unsub_dispatcher = []
        self._update_succeeded = False

    def _check_snapshot_ok(self):
        available = self.available
        if not available or not self.is_on:
            _LOGGER.warning(
                "Attempt to take snapshot when %s camera is %s",
                self.name,
                "offline" if not available else "off",
            )
            raise CannotSnapshot

    async def _async_get_image(self):
        try:
            # Send the request to snap a picture and return raw jpg data
            # Snapshot command needs a much longer read timeout than other commands.
            return await self.hass.async_add_executor_job(
                partial(
                    self._api.snapshot,
                    timeout=(COMM_TIMEOUT, SNAPSHOT_TIMEOUT),
                    stream=False,
                )
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "get image from", self.name, "camera", error)
            return None
        finally:
            self._snapshot_task = None

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        _LOGGER.debug("Take snapshot from %s", self._name)
        try:
            # Amcrest cameras only support one snapshot command at a time.
            # Hence need to wait if a previous snapshot has not yet finished.
            # Also need to check that camera is online and turned on before each wait
            # and before initiating shapshot.
            while self._snapshot_task:
                self._check_snapshot_ok()
                _LOGGER.debug("Waiting for previous snapshot from %s ...", self._name)
                await self._snapshot_task
            self._check_snapshot_ok()
            # Run snapshot command in separate Task that can't be cancelled so
            # 1) it's not possible to send another snapshot command while camera is
            #    still working on a previous one, and
            # 2) someone will be around to catch any exceptions.
            self._snapshot_task = self.hass.async_create_task(self._async_get_image())
            return await asyncio.shield(self._snapshot_task)
        except CannotSnapshot:
            return None

    async def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == "snapshot":
            return await super().handle_async_mjpeg_stream(request)

        if not self.available:
            _LOGGER.warning(
                "Attempt to stream %s when %s camera is offline",
                self._stream_source,
                self.name,
            )
            return None

        if self._stream_source == "mjpeg":
            # stream an MJPEG image stream directly from the camera
            websession = async_get_clientsession(self.hass)
            streaming_url = self._api.mjpeg_url(typeno=self._resolution)
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=CAMERA_WEB_SESSION_TIMEOUT
            )

            return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

        # streaming via ffmpeg

        streaming_url = self._rtsp_url
        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(streaming_url, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    # Entity property overrides

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the Amcrest-specific camera state attributes."""
        attr = {}
        if self._audio_enabled is not None:
            attr["audio"] = _BOOL_TO_STATE.get(self._audio_enabled)
        if self._motion_recording_enabled is not None:
            attr["motion_recording"] = _BOOL_TO_STATE.get(
                self._motion_recording_enabled
            )
        if self._color_bw is not None:
            attr[_ATTR_COLOR_BW] = self._color_bw
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_ON_OFF | SUPPORT_STREAM

    # Camera property overrides

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_recording

    @property
    def brand(self):
        """Return the camera brand."""
        return self._brand

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    async def stream_source(self):
        """Return the source of the stream."""
        return self._rtsp_url

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    # Other Entity method overrides

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to signals and add camera to list."""
        for service, params in CAMERA_SERVICES.items():
            self._unsub_dispatcher.append(
                async_dispatcher_connect(
                    self.hass,
                    service_signal(service, self.entity_id),
                    getattr(self, params[1]),
                )
            )
        self._unsub_dispatcher.append(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self._name),
                self.async_on_demand_update,
            )
        )
        self.hass.data[DATA_AMCREST][CAMERAS].append(self.entity_id)

    async def async_will_remove_from_hass(self):
        """Remove camera from list and disconnect from signals."""
        self.hass.data[DATA_AMCREST][CAMERAS].remove(self.entity_id)
        for unsub_dispatcher in self._unsub_dispatcher:
            unsub_dispatcher()

    def update(self):
        """Update entity status."""
        if not self.available or self._update_succeeded:
            if not self.available:
                self._update_succeeded = False
            return
        _LOGGER.debug("Updating %s camera", self.name)
        try:
            if self._brand is None:
                resp = self._api.vendor_information.strip()
                if resp.startswith("vendor="):
                    self._brand = resp.split("=")[-1]
                else:
                    self._brand = "unknown"
            if self._model is None:
                resp = self._api.device_type.strip()
                if resp.startswith("type="):
                    self._model = resp.split("=")[-1]
                else:
                    self._model = "unknown"
            self.is_streaming = self._get_video()
            self._is_recording = self._get_recording()
            self._motion_detection_enabled = self._get_motion_detection()
            self._audio_enabled = self._get_audio()
            self._motion_recording_enabled = self._get_motion_recording()
            self._color_bw = self._get_color_mode()
            self._rtsp_url = self._api.rtsp_url(typeno=self._resolution)
        except AmcrestError as error:
            log_update_error(_LOGGER, "get", self.name, "camera attributes", error)
            self._update_succeeded = False
        else:
            self._update_succeeded = True

    # Other Camera method overrides

    def turn_off(self):
        """Turn off camera."""
        self._enable_video(False)

    def turn_on(self):
        """Turn on camera."""
        self._enable_video(True)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._enable_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._enable_motion_detection(False)

    # Additional Amcrest Camera service methods

    async def async_enable_recording(self):
        """Call the job and enable recording."""
        await self.hass.async_add_executor_job(self._enable_recording, True)

    async def async_disable_recording(self):
        """Call the job and disable recording."""
        await self.hass.async_add_executor_job(self._enable_recording, False)

    async def async_enable_audio(self):
        """Call the job and enable audio."""
        await self.hass.async_add_executor_job(self._enable_audio, True)

    async def async_disable_audio(self):
        """Call the job and disable audio."""
        await self.hass.async_add_executor_job(self._enable_audio, False)

    async def async_enable_motion_recording(self):
        """Call the job and enable motion recording."""
        await self.hass.async_add_executor_job(self._enable_motion_recording, True)

    async def async_disable_motion_recording(self):
        """Call the job and disable motion recording."""
        await self.hass.async_add_executor_job(self._enable_motion_recording, False)

    async def async_goto_preset(self, preset):
        """Call the job and move camera to preset position."""
        await self.hass.async_add_executor_job(self._goto_preset, preset)

    async def async_set_color_bw(self, color_bw):
        """Call the job and set camera color mode."""
        await self.hass.async_add_executor_job(self._set_color_bw, color_bw)

    async def async_start_tour(self):
        """Call the job and start camera tour."""
        await self.hass.async_add_executor_job(self._start_tour, True)

    async def async_stop_tour(self):
        """Call the job and stop camera tour."""
        await self.hass.async_add_executor_job(self._start_tour, False)

    async def async_ptz_control(self, movement, travel_time):
        """Move or zoom camera in specified direction."""
        code = _ACTION[_MOV.index(movement)]

        kwargs = {"code": code, "arg1": 0, "arg2": 0, "arg3": 0}
        if code in _MOVE_1_ACTIONS:
            kwargs["arg2"] = 1
        elif code in _MOVE_2_ACTIONS:
            kwargs["arg1"] = kwargs["arg2"] = 1

        try:
            await self.hass.async_add_executor_job(
                partial(self._api.ptz_control_command, action="start", **kwargs)
            )
            await asyncio.sleep(travel_time)
            await self.hass.async_add_executor_job(
                partial(self._api.ptz_control_command, action="stop", **kwargs)
            )
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera PTZ {movement}", error
            )

    # Methods to send commands to Amcrest camera and handle errors

    def _change_setting(self, value, attr, description, action="set"):
        func = description.replace(" ", "_")
        description = f"camera {description} to {value}"
        tries = 3
        while True:
            try:
                getattr(self, f"_set_{func}")(value)
                new_value = getattr(self, f"_get_{func}")()
                if new_value != value:
                    raise AmcrestCommandFailed
            except (AmcrestError, AmcrestCommandFailed) as error:
                if tries == 1:
                    log_update_error(_LOGGER, action, self.name, description, error)
                    return
                log_update_error(
                    _LOGGER, action, self.name, description, error, logging.DEBUG
                )
            else:
                if attr:
                    setattr(self, attr, new_value)
                    self.schedule_update_ha_state()
                return
            tries -= 1

    def _get_video(self):
        return self._api.video_enabled

    def _set_video(self, enable):
        self._api.video_enabled = enable

    def _enable_video(self, enable):
        """Enable or disable camera video stream."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # recording on if video stream is being turned off.
        if self.is_recording and not enable:
            self._enable_recording(False)
        self._change_setting(enable, "is_streaming", "video")
        if self._control_light:
            self._change_light()

    def _get_recording(self):
        return self._api.record_mode == "Manual"

    def _set_recording(self, enable):
        rec_mode = {"Automatic": 0, "Manual": 1}
        self._api.record_mode = rec_mode["Manual" if enable else "Automatic"]

    def _enable_recording(self, enable):
        """Turn recording on or off."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # video stream off if recording is being turned on.
        if not self.is_streaming and enable:
            self._enable_video(True)
        self._change_setting(enable, "_is_recording", "recording")

    def _get_motion_detection(self):
        return self._api.is_motion_detector_on()

    def _set_motion_detection(self, enable):
        self._api.motion_detection = str(enable).lower()

    def _enable_motion_detection(self, enable):
        """Enable or disable motion detection."""
        self._change_setting(enable, "_motion_detection_enabled", "motion detection")

    def _get_audio(self):
        return self._api.audio_enabled

    def _set_audio(self, enable):
        self._api.audio_enabled = enable

    def _enable_audio(self, enable):
        """Enable or disable audio stream."""
        self._change_setting(enable, "_audio_enabled", "audio")
        if self._control_light:
            self._change_light()

    def _get_indicator_light(self):
        return "true" in self._api.command(
            "configManager.cgi?action=getConfig&name=LightGlobal"
        ).content.decode("utf-8")

    def _set_indicator_light(self, enable):
        self._api.command(
            f"configManager.cgi?action=setConfig&LightGlobal[0].Enable={str(enable).lower()}"
        )

    def _change_light(self):
        """Enable or disable indicator light."""
        self._change_setting(
            self._audio_enabled or self.is_streaming, None, "indicator light"
        )

    def _get_motion_recording(self):
        return self._api.is_record_on_motion_detection()

    def _set_motion_recording(self, enable):
        self._api.motion_recording = str(enable).lower()

    def _enable_motion_recording(self, enable):
        """Enable or disable motion recording."""
        self._change_setting(enable, "_motion_recording_enabled", "motion recording")

    def _goto_preset(self, preset):
        """Move camera position and zoom to preset."""
        try:
            self._api.go_to_preset(action="start", preset_point_number=preset)
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera to preset {preset}", error
            )

    def _get_color_mode(self):
        return _CBW[self._api.day_night_color]

    def _set_color_mode(self, cbw):
        self._api.day_night_color = _CBW.index(cbw)

    def _set_color_bw(self, cbw):
        """Set camera color mode."""
        self._change_setting(cbw, "_color_bw", "color mode")

    def _start_tour(self, start):
        """Start camera tour."""
        try:
            self._api.tour(start=start)
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "start" if start else "stop", self.name, "camera tour", error
            )
