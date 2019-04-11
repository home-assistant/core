"""Support for Amcrest IP cameras."""
import asyncio
import logging

from homeassistant.components.camera import (
    Camera, SUPPORT_ON_OFF, SUPPORT_STREAM)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import (
    CONF_NAME, STATE_ON, STATE_OFF)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream, async_aiohttp_proxy_web,
    async_get_clientsession)

from . import ATTR_COLOR_BW, CBW, DATA_AMCREST, STREAM_SOURCE_LIST, TIMEOUT

_LOGGER = logging.getLogger(__name__)

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST]['devices'][name]
    async_add_entities([AmcrestCam(name, device, hass)], True)


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, name, device, hass):
        """Initialize an Amcrest camera."""
        super().__init__()
        self._name = name
        self._api = device.api
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device.ffmpeg_arguments
        self._stream_source = device.stream_source
        self._resolution = device.resolution
        self._token = self._auth = device.authentication
        self._is_recording = False
        self._motion_detection_enabled = None
        self._model = None
        self._audio_enabled = None
        self._motion_recording_enabled = None
        self._color_bw = None
        self._snapshot_lock = asyncio.Lock()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        from amcrest import AmcrestError

        if not self.is_on:
            _LOGGER.error(
                'Attempt to take snaphot when %s camera is off', self.name)
            return None
        async with self._snapshot_lock:
            try:
                # Send the request to snap a picture and return raw jpg data
                response = await self.hass.async_add_executor_job(
                    self._api.snapshot, self._resolution)
                return response.data
            except AmcrestError as error:
                _LOGGER.error(
                    'Could not get image from %s camera due to error: %s',
                    self.name, error)
                return None

    async def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == STREAM_SOURCE_LIST['snapshot']:
            return await super().handle_async_mjpeg_stream(request)

        if self._stream_source == STREAM_SOURCE_LIST['mjpeg']:
            # stream an MJPEG image stream directly from the camera
            websession = async_get_clientsession(self.hass)
            streaming_url = self._api.mjpeg_url(typeno=self._resolution)
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=TIMEOUT)

            return await async_aiohttp_proxy_web(
                self.hass, request, stream_coro)

        # streaming via ffmpeg
        from haffmpeg.camera import CameraMjpeg

        streaming_url = self._api.rtsp_url(typeno=self._resolution)
        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            streaming_url, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type)
        finally:
            await stream.close()

    # Entity property overrides

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the Amcrest-spectific camera state attributes."""
        attr = {}
        if self.motion_detection_enabled is not None:
            attr['motion_detection'] = _BOOL_TO_STATE.get(
                self.motion_detection_enabled)
        if self._audio_enabled is not None:
            attr['audio'] = _BOOL_TO_STATE.get(self._audio_enabled)
        if self._motion_recording_enabled is not None:
            attr['motion_recording'] = _BOOL_TO_STATE.get(
                self._motion_recording_enabled)
        if self._color_bw is not None:
            attr[ATTR_COLOR_BW] = self._color_bw
        return attr

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
        return 'Amcrest'

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    @property
    def stream_source(self):
        """Return the source of the stream."""
        return self._api.rtsp_url(typeno=self._resolution)

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    # Other Entity method overrides

    async def async_added_to_hass(self):
        """Add camera to list."""
        self.hass.data[DATA_AMCREST]['cameras'].append(self)

    def update(self):
        """Update entity status."""
        from amcrest import AmcrestError

        _LOGGER.debug('Pulling data from %s camera', self.name)
        if self._model is None:
            try:
                self._model = self._api.device_type.split('=')[-1].strip()
            except AmcrestError as error:
                _LOGGER.error(
                    'Could not get %s camera model due to error: %s',
                    self.name, error)
                self._model = ''
        try:
            self.is_streaming = self._api.video_enabled
            self._is_recording = self._api.record_mode == 'Manual'
            self._motion_detection_enabled = (
                self._api.is_motion_detector_on())
            self._audio_enabled = self._api.audio_enabled
            self._motion_recording_enabled = (
                self._api.is_record_on_motion_detection())
            self._color_bw = CBW[self._api.day_night_color]
        except AmcrestError as error:
            _LOGGER.error(
                'Could not get %s camera attributes due to error: %s',
                self.name, error)

    # Other Camera method overrides

    def turn_off(self):
        """Turn off camera."""
        self._enable_video_stream(False)

    def turn_on(self):
        """Turn on camera."""
        self._enable_video_stream(True)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._enable_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._enable_motion_detection(False)

    # Additional Amcrest Camera service methods

    @callback
    def async_enable_recording(self):
        """Call the job and enable recording."""
        return self.hass.async_add_job(self._enable_recording, True)

    @callback
    def async_disable_recording(self):
        """Call the job and disable recording."""
        return self.hass.async_add_job(self._enable_recording, False)

    @callback
    def async_enable_audio(self):
        """Call the job and enable audio."""
        return self.hass.async_add_job(self._enable_audio, True)

    @callback
    def async_disable_audio(self):
        """Call the job and disable audio."""
        return self.hass.async_add_job(self._enable_audio, False)

    @callback
    def async_enable_motion_recording(self):
        """Call the job and enable motion recording."""
        return self.hass.async_add_job(self._enable_motion_recording, True)

    @callback
    def async_disable_motion_recording(self):
        """Call the job and disable motion recording."""
        return self.hass.async_add_job(self._enable_motion_recording, False)

    @callback
    def async_goto_preset(self, preset):
        """Call the job and move camera to preset position."""
        return self.hass.async_add_job(self._goto_preset, preset)

    @callback
    def async_set_color_bw(self, cbw):
        """Call the job and set camera color mode."""
        return self.hass.async_add_job(self._set_color_bw, cbw)

    @callback
    def async_start_tour(self):
        """Call the job and start camera tour."""
        return self.hass.async_add_job(self._start_tour, True)

    @callback
    def async_stop_tour(self):
        """Call the job and stop camera tour."""
        return self.hass.async_add_job(self._start_tour, False)

    # Methods to send commands to Amcrest camera and handle errors

    def _enable_video_stream(self, enable):
        """Enable or disable camera video stream."""
        from amcrest import AmcrestError

        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # recording on if video stream is being turned off.
        if self.is_recording and not enable:
            self._enable_recording(False)
        try:
            self._api.video_enabled = enable
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera video stream due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self.is_streaming = enable
            self.schedule_update_ha_state()

    def _enable_recording(self, enable):
        """Turn recording on or off."""
        from amcrest import AmcrestError

        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # video stream off if recording is being turned on.
        if not self.is_streaming and enable:
            self._enable_video_stream(True)
        rec_mode = {'Automatic': 0, 'Manual': 1}
        try:
            self._api.record_mode = rec_mode[
                'Manual' if enable else 'Automatic']
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera recording due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self._is_recording = enable
            self.schedule_update_ha_state()

    def _enable_motion_detection(self, enable):
        """Enable or disable motion detection."""
        from amcrest import AmcrestError

        try:
            self._api.motion_detection = str(enable).lower()
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera motion detection due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self._motion_detection_enabled = enable
            self.schedule_update_ha_state()

    def _enable_audio(self, enable):
        """Enable or disable audio stream."""
        from amcrest import AmcrestError

        try:
            self._api.audio_enabled = enable
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera audio stream due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self._audio_enabled = enable
            self.schedule_update_ha_state()

    def _enable_motion_recording(self, enable):
        """Enable or disable motion recording."""
        from amcrest import AmcrestError

        try:
            self._api.motion_recording = str(enable).lower()
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera motion recording due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self._motion_recording_enabled = enable
            self.schedule_update_ha_state()

    def _goto_preset(self, preset):
        """Move camera position and zoom to preset."""
        from amcrest import AmcrestError

        try:
            self._api.go_to_preset(
                action='start', preset_point_number=preset)
        except AmcrestError as error:
            _LOGGER.error(
                'Could not move %s camera to preset %i due to error: %s',
                self.name, preset, error)

    def _set_color_bw(self, cbw):
        """Set camera color mode."""
        from amcrest import AmcrestError

        try:
            self._api.day_night_color = CBW.index(cbw)
        except AmcrestError as error:
            _LOGGER.error(
                'Could not set %s camera color mode to %s due to error: %s',
                self.name, cbw, error)
        else:
            self._color_bw = cbw
            self.schedule_update_ha_state()

    def _start_tour(self, start):
        """Start camera tour."""
        from amcrest import AmcrestError

        try:
            self._api.tour(start=start)
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera tour due to error: %s',
                'start' if start else 'stop', self.name, error)
