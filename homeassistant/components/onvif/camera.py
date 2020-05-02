"""Support for ONVIF Cameras with FFmpeg as decoder."""
import asyncio
import datetime as dt
import os
from typing import Optional

from aiohttp.client_exceptions import ClientConnectionError, ServerDisconnectedError
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
import onvif
from onvif import ONVIFCamera, exceptions
import requests
from requests.auth import HTTPDigestAuth
import voluptuous as vol
from zeep.asyncio import AsyncTransport
from zeep.exceptions import Fault

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, DATA_FFMPEG
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream,
    async_get_clientsession,
)
import homeassistant.util.dt as dt_util

from .const import (
    ABSOLUTE_MOVE,
    ATTR_CONTINUOUS_DURATION,
    ATTR_DISTANCE,
    ATTR_MOVE_MODE,
    ATTR_PAN,
    ATTR_PRESET,
    ATTR_SPEED,
    ATTR_TILT,
    ATTR_ZOOM,
    CONF_PROFILE,
    CONF_RTSP_TRANSPORT,
    CONTINUOUS_MOVE,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DOMAIN,
    ENTITIES,
    GOTOPRESET_MOVE,
    LOGGER,
    PAN_FACTOR,
    RELATIVE_MOVE,
    SERVICE_PTZ,
    TILT_FACTOR,
    ZOOM_FACTOR,
    ZOOM_IN,
    ZOOM_OUT,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ONVIF camera video stream."""
    platform = entity_platform.current_platform.get()

    # Create PTZ service
    platform.async_register_entity_service(
        SERVICE_PTZ,
        {
            vol.Optional(ATTR_PAN): vol.In([DIR_LEFT, DIR_RIGHT]),
            vol.Optional(ATTR_TILT): vol.In([DIR_UP, DIR_DOWN]),
            vol.Optional(ATTR_ZOOM): vol.In([ZOOM_OUT, ZOOM_IN]),
            vol.Optional(ATTR_DISTANCE, default=0.1): cv.small_float,
            vol.Optional(ATTR_SPEED, default=0.5): cv.small_float,
            vol.Optional(ATTR_MOVE_MODE, default=RELATIVE_MOVE): vol.In(
                [CONTINUOUS_MOVE, RELATIVE_MOVE, ABSOLUTE_MOVE, GOTOPRESET_MOVE]
            ),
            vol.Optional(ATTR_CONTINUOUS_DURATION, default=0.5): cv.small_float,
            vol.Optional(ATTR_PRESET, default="0"): cv.string,
        },
        "async_perform_ptz",
    )

    base_config = {
        CONF_NAME: config_entry.data[CONF_NAME],
        CONF_HOST: config_entry.data[CONF_HOST],
        CONF_PORT: config_entry.data[CONF_PORT],
        CONF_USERNAME: config_entry.data[CONF_USERNAME],
        CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
        CONF_EXTRA_ARGUMENTS: config_entry.options[CONF_EXTRA_ARGUMENTS],
        CONF_RTSP_TRANSPORT: config_entry.options[CONF_RTSP_TRANSPORT],
    }

    entities = []
    for profile in config_entry.data[CONF_PROFILE]:
        config = {**base_config, CONF_PROFILE: profile}
        camera = ONVIFHassCamera(hass, config)
        await camera.async_initialize()
        entities.append(camera)

    async_add_entities(entities)
    return True


class ONVIFHassCamera(Camera):
    """An implementation of an ONVIF camera."""

    def __init__(self, hass, config):
        """Initialize an ONVIF camera."""
        super().__init__()

        LOGGER.debug("Importing dependencies")

        LOGGER.debug("Setting up the ONVIF camera component")

        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._name = config.get(CONF_NAME)
        self._ffmpeg_arguments = config.get(CONF_EXTRA_ARGUMENTS)
        self._profile_index = config.get(CONF_PROFILE)
        self._profile_token = None
        self._profile_name = None
        self._ptz_service = None
        self._input = None
        self._snapshot = None
        self.stream_options[CONF_RTSP_TRANSPORT] = config.get(CONF_RTSP_TRANSPORT)
        self._manufacturer = None
        self._model = None
        self._firmware_version = None
        self._mac = None

        LOGGER.debug(
            "Setting up the ONVIF camera device @ '%s:%s'", self._host, self._port
        )

        session = async_get_clientsession(hass)
        transport = AsyncTransport(None, session=session)
        self._camera = ONVIFCamera(
            self._host,
            self._port,
            self._username,
            self._password,
            f"{os.path.dirname(onvif.__file__)}/wsdl/",
            transport=transport,
        )

    async def async_initialize(self):
        """
        Initialize the camera.

        Initializes the camera by obtaining the input uri and connecting to
        the camera. Also retrieves the ONVIF profiles.
        """
        try:
            LOGGER.debug("Updating service addresses")
            await self._camera.update_xaddrs()

            await self.async_obtain_device_info()
            await self.async_obtain_mac_address()
            await self.async_check_date_and_time()
            await self.async_obtain_profile_token()
            await self.async_obtain_input_uri()
            await self.async_obtain_snapshot_uri()
            self.setup_ptz()
        except ClientConnectionError as err:
            LOGGER.warning(
                "Couldn't connect to camera '%s', but will retry later. Error: %s",
                self._name,
                err,
            )
            raise PlatformNotReady
        except Fault as err:
            LOGGER.error(
                "Couldn't connect to camera '%s', please verify "
                "that the credentials are correct. Error: %s",
                self._name,
                err,
            )

    async def async_obtain_device_info(self):
        """Obtain the MAC address of the camera to use as the unique ID."""
        devicemgmt = self._camera.create_devicemgmt_service()
        device_info = await devicemgmt.GetDeviceInformation()
        self._manufacturer = device_info.Manufacturer
        self._model = device_info.Model
        self._firmware_version = device_info.FirmwareVersion

    async def async_obtain_mac_address(self):
        """Obtain the MAC address of the camera to use as the unique ID."""
        devicemgmt = self._camera.create_devicemgmt_service()
        network_interfaces = await devicemgmt.GetNetworkInterfaces()
        for interface in network_interfaces:
            if interface.Enabled:
                self._mac = interface.Info.HwAddress

    async def async_check_date_and_time(self):
        """Warns if camera and system date not synced."""
        LOGGER.debug("Setting up the ONVIF device management service")
        devicemgmt = self._camera.create_devicemgmt_service()

        LOGGER.debug("Retrieving current camera date/time")
        try:
            system_date = dt_util.utcnow()
            device_time = await devicemgmt.GetSystemDateAndTime()
            if not device_time:
                LOGGER.debug(
                    """Couldn't get camera '%s' date/time.
                    GetSystemDateAndTime() return null/empty""",
                    self._name,
                )
                return

            if device_time.UTCDateTime:
                tzone = dt_util.UTC
                cdate = device_time.UTCDateTime
            else:
                tzone = (
                    dt_util.get_time_zone(device_time.TimeZone)
                    or dt_util.DEFAULT_TIME_ZONE
                )
                cdate = device_time.LocalDateTime

            if cdate is None:
                LOGGER.warning("Could not retrieve date/time on this camera")
            else:
                cam_date = dt.datetime(
                    cdate.Date.Year,
                    cdate.Date.Month,
                    cdate.Date.Day,
                    cdate.Time.Hour,
                    cdate.Time.Minute,
                    cdate.Time.Second,
                    0,
                    tzone,
                )

                cam_date_utc = cam_date.astimezone(dt_util.UTC)

                LOGGER.debug("TimeZone for date/time: %s", tzone)

                LOGGER.debug("Camera date/time: %s", cam_date)

                LOGGER.debug("Camera date/time in UTC: %s", cam_date_utc)

                LOGGER.debug("System date/time: %s", system_date)

                dt_diff = cam_date - system_date
                dt_diff_seconds = dt_diff.total_seconds()

                if dt_diff_seconds > 5:
                    LOGGER.warning(
                        "The date/time on the camera (UTC) is '%s', "
                        "which is different from the system '%s', "
                        "this could lead to authentication issues",
                        cam_date_utc,
                        system_date,
                    )
        except ServerDisconnectedError as err:
            LOGGER.warning(
                "Couldn't get camera '%s' date/time. Error: %s", self._name, err
            )

    async def async_obtain_profile_token(self):
        """Obtain profile token to use with requests."""
        try:
            media_service = self._camera.get_service("media")

            profiles = await media_service.GetProfiles()

            LOGGER.debug("Retrieved '%d' profiles", len(profiles))

            if self._profile_index >= len(profiles):
                LOGGER.warning(
                    "ONVIF Camera '%s' doesn't provide profile %d."
                    " Using the last profile.",
                    self._name,
                    self._profile_index,
                )
                self._profile_index = -1

            LOGGER.debug("Using profile index '%d'", self._profile_index)

            self._profile_token = profiles[self._profile_index].token
            self._profile_name = profiles[self._profile_index].Name
        except exceptions.ONVIFError as err:
            LOGGER.error(
                "Couldn't retrieve profile token of camera '%s'. Error: %s",
                self._name,
                err,
            )

    async def async_obtain_input_uri(self):
        """Set the input uri for the camera."""
        LOGGER.debug(
            "Connecting with ONVIF Camera: %s on port %s", self._host, self._port
        )

        try:
            LOGGER.debug("Retrieving stream uri")

            # Fix Onvif setup error on Goke GK7102 based IP camera
            # where we need to recreate media_service  #26781
            media_service = self._camera.create_media_service()

            req = media_service.create_type("GetStreamUri")
            req.ProfileToken = self._profile_token
            req.StreamSetup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }

            stream_uri = await media_service.GetStreamUri(req)
            uri_no_auth = stream_uri.Uri
            uri_for_log = uri_no_auth.replace("rtsp://", "rtsp://<user>:<password>@", 1)
            self._input = uri_no_auth.replace(
                "rtsp://", f"rtsp://{self._username}:{self._password}@", 1
            )

            LOGGER.debug(
                "ONVIF Camera Using the following URL for %s: %s",
                self._name,
                uri_for_log,
            )
        except exceptions.ONVIFError as err:
            LOGGER.error("Couldn't setup camera '%s'. Error: %s", self._name, err)

    async def async_obtain_snapshot_uri(self):
        """Set the snapshot uri for the camera."""
        LOGGER.debug(
            "Connecting with ONVIF Camera: %s on port %s", self._host, self._port
        )

        try:
            LOGGER.debug("Retrieving snapshot uri")

            # Fix Onvif setup error on Goke GK7102 based IP camera
            # where we need to recreate media_service  #26781
            media_service = self._camera.create_media_service()

            req = media_service.create_type("GetSnapshotUri")
            req.ProfileToken = self._profile_token

            try:
                snapshot_uri = await media_service.GetSnapshotUri(req)
                self._snapshot = snapshot_uri.Uri
            except ServerDisconnectedError as err:
                LOGGER.debug("Camera does not support GetSnapshotUri: %s", err)

            LOGGER.debug(
                "ONVIF Camera Using the following URL for %s snapshot: %s",
                self._name,
                self._snapshot,
            )
        except exceptions.ONVIFError as err:
            LOGGER.error("Couldn't setup camera '%s'. Error: %s", self._name, err)

    def setup_ptz(self):
        """Set up PTZ if available."""
        LOGGER.debug("Setting up the ONVIF PTZ service")
        if self._camera.get_service("ptz", create=False) is None:
            LOGGER.debug("PTZ is not available")
        else:
            self._ptz_service = self._camera.create_ptz_service()
        LOGGER.debug("Completed set up of the ONVIF camera component")

    async def async_perform_ptz(
        self,
        distance,
        speed,
        move_mode,
        continuous_duration,
        preset,
        pan=None,
        tilt=None,
        zoom=None,
    ):
        """Perform a PTZ action on the camera."""
        if self._ptz_service is None:
            LOGGER.warning("PTZ actions are not supported on camera '%s'", self._name)
            return

        pan_val = distance * PAN_FACTOR.get(pan, 0)
        tilt_val = distance * TILT_FACTOR.get(tilt, 0)
        zoom_val = distance * ZOOM_FACTOR.get(zoom, 0)
        speed_val = speed
        preset_val = preset
        LOGGER.debug(
            "Calling %s PTZ | Pan = %4.2f | Tilt = %4.2f | Zoom = %4.2f | Speed = %4.2f | Preset = %s",
            move_mode,
            pan_val,
            tilt_val,
            zoom_val,
            speed_val,
            preset_val,
        )
        try:
            req = self._ptz_service.create_type(move_mode)
            req.ProfileToken = self._profile_token
            if move_mode == CONTINUOUS_MOVE:
                req.Velocity = {
                    "PanTilt": {"x": pan_val, "y": tilt_val},
                    "Zoom": {"x": zoom_val},
                }

                await self._ptz_service.ContinuousMove(req)
                await asyncio.sleep(continuous_duration)
                req = self._ptz_service.create_type("Stop")
                req.ProfileToken = self._profile_token
                await self._ptz_service.Stop({"ProfileToken": req.ProfileToken})
            elif move_mode == RELATIVE_MOVE:
                req.Translation = {
                    "PanTilt": {"x": pan_val, "y": tilt_val},
                    "Zoom": {"x": zoom_val},
                }
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await self._ptz_service.RelativeMove(req)
            elif move_mode == ABSOLUTE_MOVE:
                req.Position = {
                    "PanTilt": {"x": pan_val, "y": tilt_val},
                    "Zoom": {"x": zoom_val},
                }
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await self._ptz_service.AbsoluteMove(req)
            elif move_mode == GOTOPRESET_MOVE:
                req.PresetToken = preset_val
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await self._ptz_service.GotoPreset(req)
        except exceptions.ONVIFError as err:
            if "Bad Request" in err.reason:
                self._ptz_service = None
                LOGGER.debug("Camera '%s' doesn't support PTZ.", self._name)
            else:
                LOGGER.error("Error trying to perform PTZ action: %s", err)

    async def async_added_to_hass(self):
        """Handle entity addition to hass."""
        LOGGER.debug("Camera '%s' added to hass", self._name)

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
            self.hass.data[DOMAIN][ENTITIES] = []
        self.hass.data[DOMAIN][ENTITIES].append(self)

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        LOGGER.debug("Retrieving image from camera '%s'", self._name)
        image = None

        if self._snapshot is not None:
            auth = None
            if self._username and self._password:
                auth = HTTPDigestAuth(self._username, self._password)

            def fetch():
                """Read image from a URL."""
                try:
                    response = requests.get(self._snapshot, timeout=5, auth=auth)
                    if response.status_code < 300:
                        return response.content
                except requests.exceptions.RequestException as error:
                    LOGGER.error(
                        "Fetch snapshot image failed from %s, falling back to FFmpeg; %s",
                        self._name,
                        error,
                    )

                return None

            image = await self.hass.async_add_job(fetch)

        if image is None:
            # Don't keep trying the snapshot URL
            self._snapshot = None

            ffmpeg = ImageFrame(self.hass.data[DATA_FFMPEG].binary, loop=self.hass.loop)
            image = await asyncio.shield(
                ffmpeg.get_image(
                    self._input,
                    output_format=IMAGE_JPEG,
                    extra_cmd=self._ffmpeg_arguments,
                )
            )

        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        LOGGER.debug("Handling mjpeg stream from camera '%s'", self._name)

        ffmpeg_manager = self.hass.data[DATA_FFMPEG]
        stream = CameraMjpeg(ffmpeg_manager.binary, loop=self.hass.loop)

        await stream.open_camera(self._input, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                ffmpeg_manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    @property
    def supported_features(self):
        """Return supported features."""
        if self._input:
            return SUPPORT_STREAM
        return 0

    async def stream_source(self):
        """Return the stream source."""
        return self._input

    @property
    def name(self):
        """Return the name of this camera."""
        return f"{self._name} - {self._profile_name}"

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        if self._profile_index:
            return f"{self._mac}_{self._profile_index}"
        return self._mac

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": self._manufacturer,
            "model": self._model,
            "sw_version": self._firmware_version,
        }
