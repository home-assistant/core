"""Support for Amcrest IP cameras."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from amcrest import AmcrestError
from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    Camera,
    CameraEntityFeature,
)
from homeassistant.components.ffmpeg import FFmpegManager, get_ffmpeg_manager
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream,
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CAMERA_WEB_SESSION_TIMEOUT,
    CAMERAS,
    COMM_TIMEOUT,
    DATA_AMCREST,
    DEVICES,
    DOMAIN,
    RESOLUTION_TO_STREAM,
    SERVICE_UPDATE,
    SNAPSHOT_TIMEOUT,
)
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

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

_SRV_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})
_SRV_GOTO_SCHEMA = _SRV_SCHEMA.extend(
    {vol.Required(_ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1))}
)
_SRV_CBW_SCHEMA = _SRV_SCHEMA.extend({vol.Required(_ATTR_COLOR_BW): vol.In(_CBW)})
_SRV_PTZ_SCHEMA = _SRV_SCHEMA.extend(
    {
        vol.Required(_ATTR_PTZ_MOV): vol.In(_MOV),
        vol.Optional(_ATTR_PTZ_TT, default=_DEFAULT_TT): cv.small_float,
    }
)

CAMERA_SERVICES = {
    _SRV_EN_REC: (_SRV_SCHEMA, "async_enable_recording", ()),
    _SRV_DS_REC: (_SRV_SCHEMA, "async_disable_recording", ()),
    _SRV_EN_AUD: (_SRV_SCHEMA, "async_enable_audio", ()),
    _SRV_DS_AUD: (_SRV_SCHEMA, "async_disable_audio", ()),
    _SRV_EN_MOT_REC: (_SRV_SCHEMA, "async_enable_motion_recording", ()),
    _SRV_DS_MOT_REC: (_SRV_SCHEMA, "async_disable_motion_recording", ()),
    _SRV_GOTO: (_SRV_GOTO_SCHEMA, "async_goto_preset", (_ATTR_PRESET,)),
    _SRV_CBW: (_SRV_CBW_SCHEMA, "async_set_color_bw", (_ATTR_COLOR_BW,)),
    _SRV_TOUR_ON: (_SRV_SCHEMA, "async_start_tour", ()),
    _SRV_TOUR_OFF: (_SRV_SCHEMA, "async_stop_tour", ()),
    _SRV_PTZ_CTRL: (
        _SRV_PTZ_SCHEMA,
        "async_ptz_control",
        (_ATTR_PTZ_MOV, _ATTR_PTZ_TT),
    ),
}

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    entity = AmcrestCam(name, device, get_ffmpeg_manager(hass))

    # 2021.9.0 introduced unique id's for the camera entity, but these were not
    # unique for different resolution streams.  If any cameras were configured
    # with this version, update the old entity with the new unique id.
    serial_number = await device.api.async_serial_number
    serial_number = serial_number.strip()
    registry = entity_registry.async_get(hass)
    entity_id = registry.async_get_entity_id(CAMERA_DOMAIN, DOMAIN, serial_number)
    if entity_id is not None:
        _LOGGER.debug("Updating unique id for camera %s", entity_id)
        new_unique_id = f"{serial_number}-{device.resolution}-{device.channel}"
        registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    async_add_entities([entity], True)


class CannotSnapshot(Exception):
    """Conditions are not valid for taking a snapshot."""


class AmcrestCommandFailed(Exception):
    """Amcrest camera command did not work."""


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    _attr_should_poll = True  # Cameras default to False
    _attr_supported_features = CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM

    def __init__(self, name: str, device: AmcrestDevice, ffmpeg: FFmpegManager) -> None:
        """Initialize an Amcrest camera."""
        super().__init__()
        self._name = name
        self._api = device.api
        self._ffmpeg = ffmpeg
        self._ffmpeg_arguments = device.ffmpeg_arguments
        self._stream_source = device.stream_source
        self._resolution = device.resolution
        self._channel = device.channel
        self._token = self._auth = device.authentication
        self._control_light = device.control_light
        self._is_recording: bool = False
        self._motion_detection_enabled: bool = False
        self._brand: str | None = None
        self._model: str | None = None
        self._audio_enabled: bool | None = None
        self._motion_recording_enabled: bool | None = None
        self._color_bw: str | None = None
        self._rtsp_url: str | None = None
        self._snapshot_task: asyncio.tasks.Task | None = None
        self._unsub_dispatcher: list[Callable[[], None]] = []

    def _check_snapshot_ok(self) -> None:
        available = self.available
        if not available or not self.is_on:
            _LOGGER.warning(
                "Attempt to take snapshot when %s camera is %s",
                self.name,
                "offline" if not available else "off",
            )
            raise CannotSnapshot

    async def _async_get_image(self) -> bytes | None:
        try:
            # Send the request to snap a picture and return raw jpg data
            # Snapshot command needs a much longer read timeout than other commands.
            return await self._api.async_snapshot(
                timeout=(COMM_TIMEOUT, SNAPSHOT_TIMEOUT)
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "get image from", self.name, "camera", error)
            return None
        finally:
            self._snapshot_task = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        _LOGGER.debug("Take snapshot from %s", self._name)
        try:
            # Amcrest cameras only support one snapshot command at a time.
            # Hence need to wait if a previous snapshot has not yet finished.
            # Also need to check that camera is online and turned on before each wait
            # and before initiating shapshot.
            while self._snapshot_task:
                self._check_snapshot_ok()
                _LOGGER.debug("Waiting for previous snapshot from %s", self._name)
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

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
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
        assert self._rtsp_url is not None
        streaming_url = self._rtsp_url
        stream = CameraMjpeg(self._ffmpeg.binary)
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
    def name(self) -> str:
        """Return the name of this camera."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.available

    # Camera property overrides

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self._is_recording

    @property
    def brand(self) -> str | None:
        """Return the camera brand."""
        return self._brand

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    @property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._model

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return self._rtsp_url

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self.is_streaming

    # Other Entity method overrides

    async def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Subscribe to signals and add camera to list."""
        self._unsub_dispatcher.extend(
            async_dispatcher_connect(
                self.hass,
                service_signal(service, self.entity_id),
                getattr(self, callback_name),
            )
            for service, (_, callback_name, _) in CAMERA_SERVICES.items()
        )
        self._unsub_dispatcher.append(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self.name),
                self.async_on_demand_update,
            )
        )
        self.hass.data[DATA_AMCREST][CAMERAS].append(self.entity_id)

    async def async_will_remove_from_hass(self) -> None:
        """Remove camera from list and disconnect from signals."""
        self.hass.data[DATA_AMCREST][CAMERAS].remove(self.entity_id)
        for unsub_dispatcher in self._unsub_dispatcher:
            unsub_dispatcher()

    async def async_update(self) -> None:
        """Update entity status."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s camera", self.name)
        try:
            if self._brand is None:
                resp = await self._api.async_vendor_information
                _LOGGER.debug("Assigned brand=%s", resp)
                if resp:
                    self._brand = resp
                else:
                    self._brand = "unknown"
            if self._model is None:
                resp = await self._api.async_device_type
                _LOGGER.debug("Assigned model=%s", resp)
                if resp:
                    self._model = resp
                else:
                    self._model = "unknown"
            if self._attr_unique_id is None:
                serial_number = (await self._api.async_serial_number).strip()
                if serial_number:
                    self._attr_unique_id = (
                        f"{serial_number}-{self._resolution}-{self._channel}"
                    )
                    _LOGGER.debug("Assigned unique_id=%s", self._attr_unique_id)
            if self._rtsp_url is None:
                self._rtsp_url = await self._api.async_rtsp_url(typeno=self._resolution)

            (
                self._attr_is_streaming,
                self._is_recording,
                self._motion_detection_enabled,
                self._audio_enabled,
                self._motion_recording_enabled,
                self._color_bw,
            ) = await asyncio.gather(
                self._async_get_video(),
                self._async_get_recording(),
                self._async_get_motion_detection(),
                self._async_get_audio(),
                self._async_get_motion_recording(),
                self._async_get_color_mode(),
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "get", self.name, "camera attributes", error)

    # Other Camera method overrides

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self._async_enable_video(False)

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self._async_enable_video(True)

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        await self._async_enable_motion_detection(True)

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        await self._async_enable_motion_detection(False)

    # Additional Amcrest Camera service methods

    async def async_enable_recording(self) -> None:
        """Call the job and enable recording."""
        await self._async_enable_recording(True)

    async def async_disable_recording(self) -> None:
        """Call the job and disable recording."""
        await self._async_enable_recording(False)

    async def async_enable_audio(self) -> None:
        """Call the job and enable audio."""
        await self._async_enable_audio(True)

    async def async_disable_audio(self) -> None:
        """Call the job and disable audio."""
        await self._async_enable_audio(False)

    async def async_enable_motion_recording(self) -> None:
        """Call the job and enable motion recording."""
        await self._async_enable_motion_recording(True)

    async def async_disable_motion_recording(self) -> None:
        """Call the job and disable motion recording."""
        await self._async_enable_motion_recording(False)

    async def async_goto_preset(self, preset: int) -> None:
        """Call the job and move camera to preset position."""
        await self._async_goto_preset(preset)

    async def async_set_color_bw(self, color_bw: str) -> None:
        """Call the job and set camera color mode."""
        await self._async_set_color_bw(color_bw)

    async def async_start_tour(self) -> None:
        """Call the job and start camera tour."""
        await self._async_start_tour(True)

    async def async_stop_tour(self) -> None:
        """Call the job and stop camera tour."""
        await self._async_start_tour(False)

    async def async_ptz_control(self, movement: str, travel_time: float) -> None:
        """Move or zoom camera in specified direction."""
        code = _ACTION[_MOV.index(movement)]

        kwargs = {"code": code, "arg1": 0, "arg2": 0, "arg3": 0}
        if code in _MOVE_1_ACTIONS:
            kwargs["arg2"] = 1
        elif code in _MOVE_2_ACTIONS:
            kwargs["arg1"] = kwargs["arg2"] = 1

        try:
            await self._api.async_ptz_control_command(action="start", **kwargs)  # type: ignore[arg-type]
            await asyncio.sleep(travel_time)
            await self._api.async_ptz_control_command(action="stop", **kwargs)  # type: ignore[arg-type]
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera PTZ {movement}", error
            )

    # Methods to send commands to Amcrest camera and handle errors

    async def _async_change_setting(
        self, value: str | bool, description: str, attr: str | None = None
    ) -> None:
        func = description.replace(" ", "_")
        description = f"camera {description} to {value}"
        action = "set"
        max_tries = 3
        for tries in range(max_tries, 0, -1):
            try:
                await getattr(self, f"_async_set_{func}")(value)
                new_value = await getattr(self, f"_async_get_{func}")()
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

    async def _async_get_video(self) -> bool:
        return await self._api.async_is_video_enabled(
            channel=0, stream=RESOLUTION_TO_STREAM[self._resolution]
        )

    async def _async_set_video(self, enable: bool) -> None:
        await self._api.async_set_video_enabled(
            enable, channel=0, stream=RESOLUTION_TO_STREAM[self._resolution]
        )

    async def _async_enable_video(self, enable: bool) -> None:
        """Enable or disable camera video stream."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # recording on if video stream is being turned off.
        if self.is_recording and not enable:
            await self._async_enable_recording(False)
        await self._async_change_setting(enable, "video", "_attr_is_streaming")
        if self._control_light:
            await self._async_change_light()

    async def _async_get_recording(self) -> bool:
        return (await self._api.async_record_mode) == "Manual"

    async def _async_set_recording(self, enable: bool) -> None:
        rec_mode = {"Automatic": 0, "Manual": 1}
        # The property has a str type, but setter has int type, which causes mypy confusion
        await self._api.async_set_record_mode(
            rec_mode["Manual" if enable else "Automatic"]
        )

    async def _async_enable_recording(self, enable: bool) -> None:
        """Turn recording on or off."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # video stream off if recording is being turned on.
        if not self.is_streaming and enable:
            await self._async_enable_video(True)
        await self._async_change_setting(enable, "recording", "_is_recording")

    async def _async_get_motion_detection(self) -> bool:
        return await self._api.async_is_motion_detector_on()

    async def _async_set_motion_detection(self, enable: bool) -> None:
        # The property has a str type, but setter has bool type, which causes mypy confusion
        await self._api.async_set_motion_detection(enable)

    async def _async_enable_motion_detection(self, enable: bool) -> None:
        """Enable or disable motion detection."""
        await self._async_change_setting(
            enable, "motion detection", "_motion_detection_enabled"
        )

    async def _async_get_audio(self) -> bool:
        return await self._api.async_is_audio_enabled(
            channel=0, stream=RESOLUTION_TO_STREAM[self._resolution]
        )

    async def _async_set_audio(self, enable: bool) -> None:
        await self._api.async_set_audio_enabled(
            enable, channel=0, stream=RESOLUTION_TO_STREAM[self._resolution]
        )

    async def _async_enable_audio(self, enable: bool) -> None:
        """Enable or disable audio stream."""
        await self._async_change_setting(enable, "audio", "_audio_enabled")
        if self._control_light:
            await self._async_change_light()

    async def _async_get_indicator_light(self) -> bool:
        return (
            "true"
            in (
                await self._api.async_command(
                    "configManager.cgi?action=getConfig&name=LightGlobal"
                )
            ).content.decode()
        )

    async def _async_set_indicator_light(self, enable: bool) -> None:
        await self._api.async_command(
            f"configManager.cgi?action=setConfig&LightGlobal[0].Enable={str(enable).lower()}"
        )

    async def _async_change_light(self) -> None:
        """Enable or disable indicator light."""
        await self._async_change_setting(
            self._audio_enabled or self.is_streaming, "indicator light"
        )

    async def _async_get_motion_recording(self) -> bool:
        return await self._api.async_is_record_on_motion_detection()

    async def _async_set_motion_recording(self, enable: bool) -> None:
        await self._api.async_set_motion_recording(enable)

    async def _async_enable_motion_recording(self, enable: bool) -> None:
        """Enable or disable motion recording."""
        await self._async_change_setting(
            enable, "motion recording", "_motion_recording_enabled"
        )

    async def _async_goto_preset(self, preset: int) -> None:
        """Move camera position and zoom to preset."""
        try:
            await self._api.async_go_to_preset(preset_point_number=preset)
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera to preset {preset}", error
            )

    async def _async_get_color_mode(self) -> str:
        return _CBW[await self._api.async_day_night_color]

    async def _async_set_color_mode(self, cbw: str) -> None:
        await self._api.async_set_day_night_color(_CBW.index(cbw), channel=0)

    async def _async_set_color_bw(self, cbw: str) -> None:
        """Set camera color mode."""
        await self._async_change_setting(cbw, "color mode", "_color_bw")

    async def _async_start_tour(self, start: bool) -> None:
        """Start camera tour."""
        try:
            await self._api.async_tour(start=start)
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "start" if start else "stop", self.name, "camera tour", error
            )
