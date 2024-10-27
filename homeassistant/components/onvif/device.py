"""ONVIF device abstraction."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import datetime as dt
import os
import time
from typing import Any

from httpx import RequestError
import onvif
from onvif import ONVIFCamera
from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault, TransportError, XMLParseError, XMLSyntaxError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util

from .const import (
    ABSOLUTE_MOVE,
    CONF_ENABLE_WEBHOOKS,
    CONTINUOUS_MOVE,
    DEFAULT_ENABLE_WEBHOOKS,
    GET_CAPABILITIES_EXCEPTIONS,
    GOTOPRESET_MOVE,
    LOGGER,
    PAN_FACTOR,
    RELATIVE_MOVE,
    STOP_MOVE,
    TILT_FACTOR,
    ZOOM_FACTOR,
)
from .event import EventManager
from .models import PTZ, Capabilities, DeviceInfo, Profile, Resolution, Video


class ONVIFDevice:
    """Manages an ONVIF device."""

    device: ONVIFCamera
    events: EventManager

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the device."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry
        self._original_options = dict(config_entry.options)
        self.available: bool = True

        self.info: DeviceInfo = DeviceInfo()
        self.capabilities: Capabilities = Capabilities()
        self.onvif_capabilities: dict[str, Any] | None = None
        self.profiles: list[Profile] = []
        self.max_resolution: int = 0
        self.platforms: list[Platform] = []

        self._dt_diff_seconds: float = 0

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        if self._original_options != entry.options:
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    @property
    def name(self) -> str:
        """Return the name of this device."""
        return self.config_entry.data[CONF_NAME]

    @property
    def host(self) -> str:
        """Return the host of this device."""
        return self.config_entry.data[CONF_HOST]

    @property
    def port(self) -> int:
        """Return the port of this device."""
        return self.config_entry.data[CONF_PORT]

    @property
    def username(self) -> str:
        """Return the username of this device."""
        return self.config_entry.data[CONF_USERNAME]

    @property
    def password(self) -> str:
        """Return the password of this device."""
        return self.config_entry.data[CONF_PASSWORD]

    async def async_setup(self) -> None:
        """Set up the device."""
        self.device = get_device(
            self.hass,
            host=self.config_entry.data[CONF_HOST],
            port=self.config_entry.data[CONF_PORT],
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
        )

        # Get all device info
        await self.device.update_xaddrs()
        LOGGER.debug("%s: xaddrs = %s", self.name, self.device.xaddrs)

        # Get device capabilities
        self.onvif_capabilities = await self.device.get_capabilities()

        await self.async_check_date_and_time()

        # Create event manager
        assert self.config_entry.unique_id
        self.events = EventManager(self.hass, self.device, self.config_entry, self.name)

        # Fetch basic device info and capabilities
        self.info = await self.async_get_device_info()
        LOGGER.debug("%s: camera info = %s", self.name, self.info)

        #
        # We need to check capabilities before profiles, because we need the data
        # from capabilities to determine profiles correctly.
        #
        # We no longer initialize events in capabilities to avoid the problem
        # where cameras become slow to respond for a bit after starting events, and
        # instead we start events last and than update capabilities.
        #
        LOGGER.debug("%s: fetching initial capabilities", self.name)
        self.capabilities = await self.async_get_capabilities()

        LOGGER.debug("%s: fetching profiles", self.name)
        self.profiles = await self.async_get_profiles()
        LOGGER.debug("Camera %s profiles = %s", self.name, self.profiles)

        # No camera profiles to add
        if not self.profiles:
            raise ONVIFError("No camera profiles found")

        if self.capabilities.ptz:
            LOGGER.debug("%s: creating PTZ service", self.name)
            await self.device.create_ptz_service()

        # Determine max resolution from profiles
        self.max_resolution = max(
            profile.video.resolution.width
            for profile in self.profiles
            if profile.video.encoding == "H264"
        )

        # Start events last since some cameras become slow to respond
        # for a bit after starting events
        LOGGER.debug("%s: starting events", self.name)
        self.capabilities.events = await self.async_start_events()
        LOGGER.debug("Camera %s capabilities = %s", self.name, self.capabilities)

        # Bind the listener to the ONVIFDevice instance since
        # async_update_listener only creates a weak reference to the listener
        # and we need to make sure it doesn't get garbage collected since only
        # the ONVIFDevice instance is stored in hass.data
        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(self._async_update_listener)
        )

    async def async_stop(self, event=None):
        """Shut it all down."""
        if self.events:
            await self.events.async_stop()
        await self.device.close()

    async def async_manually_set_date_and_time(self) -> None:
        """Set Date and Time Manually using SetSystemDateAndTime command."""
        device_mgmt = await self.device.create_devicemgmt_service()

        # Retrieve DateTime object from camera to use as template for Set operation
        device_time = await device_mgmt.GetSystemDateAndTime()

        system_date = dt_util.utcnow()
        LOGGER.debug("System date (UTC): %s", system_date)

        dt_param = device_mgmt.create_type("SetSystemDateAndTime")
        dt_param.DateTimeType = "Manual"
        # Retrieve DST setting from system
        dt_param.DaylightSavings = bool(time.localtime().tm_isdst)
        dt_param.UTCDateTime = {
            "Date": {
                "Year": system_date.year,
                "Month": system_date.month,
                "Day": system_date.day,
            },
            "Time": {
                "Hour": system_date.hour,
                "Minute": system_date.minute,
                "Second": system_date.second,
            },
        }
        # Retrieve timezone from system
        system_timezone = str(system_date.astimezone().tzinfo)
        timezone_names: list[str | None] = [system_timezone]
        if (time_zone := device_time.TimeZone) and system_timezone != time_zone.TZ:
            timezone_names.append(time_zone.TZ)
        timezone_names.append(None)
        timezone_max_idx = len(timezone_names) - 1
        LOGGER.debug(
            "%s: SetSystemDateAndTime: timezone_names:%s", self.name, timezone_names
        )
        for idx, timezone_name in enumerate(timezone_names):
            dt_param.TimeZone = timezone_name
            LOGGER.debug("%s: SetSystemDateAndTime: %s", self.name, dt_param)
            try:
                await device_mgmt.SetSystemDateAndTime(dt_param)
                LOGGER.debug("%s: SetSystemDateAndTime: success", self.name)
            # Some cameras don't support setting the timezone and will throw an IndexError
            # if we try to set it. If we get an error, try again without the timezone.
            except (IndexError, Fault):
                if idx == timezone_max_idx:
                    raise
            else:
                return

    async def async_check_date_and_time(self) -> None:
        """Warns if device and system date not synced."""
        LOGGER.debug("%s: Setting up the ONVIF device management service", self.name)
        device_mgmt = await self.device.create_devicemgmt_service()
        system_date = dt_util.utcnow()

        LOGGER.debug("%s: Retrieving current device date/time", self.name)
        try:
            device_time = await device_mgmt.GetSystemDateAndTime()
        except RequestError as err:
            LOGGER.warning(
                "Couldn't get device '%s' date/time. Error: %s", self.name, err
            )
            return

        if not device_time:
            LOGGER.debug(
                """Couldn't get device '%s' date/time.
                GetSystemDateAndTime() return null/empty""",
                self.name,
            )
            return

        LOGGER.debug("%s: Device time: %s", self.name, device_time)

        tzone = dt_util.get_default_time_zone()
        cdate = device_time.LocalDateTime
        if device_time.UTCDateTime:
            tzone = dt_util.UTC
            cdate = device_time.UTCDateTime
        elif device_time.TimeZone:
            tzone = await dt_util.async_get_time_zone(device_time.TimeZone.TZ) or tzone

        if cdate is None:
            LOGGER.warning("%s: Could not retrieve date/time on this camera", self.name)
            return

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

        LOGGER.debug(
            "%s: Device date/time: %s | System date/time: %s",
            self.name,
            cam_date_utc,
            system_date,
        )

        dt_diff = cam_date - system_date
        self._dt_diff_seconds = dt_diff.total_seconds()

        # It could be off either direction, so we need to check the absolute value
        if abs(self._dt_diff_seconds) < 5:
            return

        if device_time.DateTimeType != "Manual":
            self._async_log_time_out_of_sync(cam_date_utc, system_date)
            return

        # Set Date and Time ourselves if Date and Time is set manually in the camera.
        try:
            await self.async_manually_set_date_and_time()
        except (RequestError, TransportError, IndexError, Fault):
            LOGGER.warning("%s: Could not sync date/time on this camera", self.name)
            self._async_log_time_out_of_sync(cam_date_utc, system_date)

    @callback
    def _async_log_time_out_of_sync(
        self, cam_date_utc: dt.datetime, system_date: dt.datetime
    ) -> None:
        """Log a warning if the camera and system date/time are not synced."""
        LOGGER.warning(
            (
                "The date/time on %s (UTC) is '%s', "
                "which is different from the system '%s', "
                "this could lead to authentication issues"
            ),
            self.name,
            cam_date_utc,
            system_date,
        )

    async def async_get_device_info(self) -> DeviceInfo:
        """Obtain information about this device."""
        device_mgmt = await self.device.create_devicemgmt_service()
        manufacturer = None
        model = None
        firmware_version = None
        serial_number = None
        try:
            device_info = await device_mgmt.GetDeviceInformation()
        except (XMLParseError, XMLSyntaxError, TransportError) as ex:
            # Some cameras have invalid UTF-8 in their device information (TransportError)
            # and others have completely invalid XML (XMLParseError, XMLSyntaxError)
            LOGGER.warning("%s: Failed to fetch device information: %s", self.name, ex)
        else:
            manufacturer = device_info.Manufacturer
            model = device_info.Model
            firmware_version = device_info.FirmwareVersion
            serial_number = device_info.SerialNumber

        # Grab the last MAC address for backwards compatibility
        mac = None
        try:
            network_interfaces = await device_mgmt.GetNetworkInterfaces()
            for interface in network_interfaces:
                if interface.Enabled:
                    mac = interface.Info.HwAddress
        except Fault as fault:
            if "not implemented" not in fault.message:
                raise

            LOGGER.debug(
                "Couldn't get network interfaces from ONVIF device '%s'. Error: %s",
                self.name,
                fault,
            )

        return DeviceInfo(
            manufacturer,
            model,
            firmware_version,
            serial_number,
            mac,
        )

    async def async_get_capabilities(self):
        """Obtain information about the available services on the device."""
        snapshot = False
        with suppress(*GET_CAPABILITIES_EXCEPTIONS):
            media_service = await self.device.create_media_service()
            media_capabilities = await media_service.GetServiceCapabilities()
            snapshot = media_capabilities and media_capabilities.SnapshotUri

        ptz = False
        with suppress(*GET_CAPABILITIES_EXCEPTIONS):
            self.device.get_definition("ptz")
            ptz = True

        imaging = False
        with suppress(*GET_CAPABILITIES_EXCEPTIONS):
            await self.device.create_imaging_service()
            imaging = True

        return Capabilities(snapshot=snapshot, ptz=ptz, imaging=imaging)

    async def async_start_events(self):
        """Start the event handler."""
        with suppress(*GET_CAPABILITIES_EXCEPTIONS, XMLParseError):
            onvif_capabilities = self.onvif_capabilities or {}
            pull_point_support = (onvif_capabilities.get("Events") or {}).get(
                "WSPullPointSupport"
            )
            LOGGER.debug("%s: WSPullPointSupport: %s", self.name, pull_point_support)
            # Even if the camera claims it does not support PullPoint, try anyway
            # since at least some AXIS and Bosch models do. The reverse is also
            # true where some cameras claim they support PullPoint but don't so
            # the only way to know is to try.
            return await self.events.async_start(
                True,
                self.config_entry.options.get(
                    CONF_ENABLE_WEBHOOKS, DEFAULT_ENABLE_WEBHOOKS
                ),
            )

        return False

    async def async_get_profiles(self) -> list[Profile]:
        """Obtain media profiles for this device."""
        media_service = await self.device.create_media_service()
        LOGGER.debug("%s: xaddr for media_service: %s", self.name, media_service.xaddr)
        try:
            result = await media_service.GetProfiles()
        except GET_CAPABILITIES_EXCEPTIONS:
            LOGGER.debug(
                "%s: Could not get profiles from ONVIF device", self.name, exc_info=True
            )
            raise
        profiles: list[Profile] = []

        if not isinstance(result, list):
            return profiles

        for key, onvif_profile in enumerate(result):
            # Only add H264 profiles
            if (
                not onvif_profile.VideoEncoderConfiguration
                or onvif_profile.VideoEncoderConfiguration.Encoding != "H264"
            ):
                continue

            profile = Profile(
                key,
                onvif_profile.token,
                onvif_profile.Name,
                Video(
                    onvif_profile.VideoEncoderConfiguration.Encoding,
                    Resolution(
                        onvif_profile.VideoEncoderConfiguration.Resolution.Width,
                        onvif_profile.VideoEncoderConfiguration.Resolution.Height,
                    ),
                ),
            )

            # Configure PTZ options
            if self.capabilities.ptz and onvif_profile.PTZConfiguration:
                profile.ptz = PTZ(
                    onvif_profile.PTZConfiguration.DefaultContinuousPanTiltVelocitySpace
                    is not None,
                    onvif_profile.PTZConfiguration.DefaultRelativePanTiltTranslationSpace
                    is not None,
                    onvif_profile.PTZConfiguration.DefaultAbsolutePantTiltPositionSpace
                    is not None,
                )

                try:
                    ptz_service = await self.device.create_ptz_service()
                    presets = await ptz_service.GetPresets(profile.token)
                    profile.ptz.presets = [preset.token for preset in presets if preset]
                except GET_CAPABILITIES_EXCEPTIONS:
                    # It's OK if Presets aren't supported
                    profile.ptz.presets = []

            # Configure Imaging options
            if self.capabilities.imaging and onvif_profile.VideoSourceConfiguration:
                profile.video_source_token = (
                    onvif_profile.VideoSourceConfiguration.SourceToken
                )

            profiles.append(profile)

        return profiles

    async def async_get_stream_uri(self, profile: Profile) -> str:
        """Get the stream URI for a specified profile."""
        media_service = await self.device.create_media_service()
        req = media_service.create_type("GetStreamUri")
        req.ProfileToken = profile.token
        req.StreamSetup = {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"},
        }
        result = await media_service.GetStreamUri(req)
        return result.Uri

    async def async_perform_ptz(
        self,
        profile: Profile,
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
        if not self.capabilities.ptz:
            LOGGER.warning("PTZ actions are not supported on device '%s'", self.name)
            return

        ptz_service = await self.device.create_ptz_service()

        pan_val = distance * PAN_FACTOR.get(pan, 0)
        tilt_val = distance * TILT_FACTOR.get(tilt, 0)
        zoom_val = distance * ZOOM_FACTOR.get(zoom, 0)
        speed_val = speed
        preset_val = preset
        LOGGER.debug(
            (
                "Calling %s PTZ | Pan = %4.2f | Tilt = %4.2f | Zoom = %4.2f | Speed ="
                " %4.2f | Preset = %s"
            ),
            move_mode,
            pan_val,
            tilt_val,
            zoom_val,
            speed_val,
            preset_val,
        )
        try:
            req = ptz_service.create_type(move_mode)
            req.ProfileToken = profile.token
            if move_mode == CONTINUOUS_MOVE:
                # Guard against unsupported operation
                if not profile.ptz or not profile.ptz.continuous:
                    LOGGER.warning(
                        "ContinuousMove not supported on device '%s'", self.name
                    )
                    return

                velocity = {}
                if pan is not None or tilt is not None:
                    velocity["PanTilt"] = {"x": pan_val, "y": tilt_val}
                if zoom is not None:
                    velocity["Zoom"] = {"x": zoom_val}

                req.Velocity = velocity

                await ptz_service.ContinuousMove(req)
                await asyncio.sleep(continuous_duration)
                req = ptz_service.create_type("Stop")
                req.ProfileToken = profile.token
                await ptz_service.Stop(
                    {"ProfileToken": req.ProfileToken, "PanTilt": True, "Zoom": False}
                )
            elif move_mode == RELATIVE_MOVE:
                # Guard against unsupported operation
                if not profile.ptz or not profile.ptz.relative:
                    LOGGER.warning(
                        "RelativeMove not supported on device '%s'", self.name
                    )
                    return

                req.Translation = {
                    "PanTilt": {"x": pan_val, "y": tilt_val},
                    "Zoom": {"x": zoom_val},
                }
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await ptz_service.RelativeMove(req)
            elif move_mode == ABSOLUTE_MOVE:
                # Guard against unsupported operation
                if not profile.ptz or not profile.ptz.absolute:
                    LOGGER.warning(
                        "AbsoluteMove not supported on device '%s'", self.name
                    )
                    return

                req.Position = {
                    "PanTilt": {"x": pan_val, "y": tilt_val},
                    "Zoom": {"x": zoom_val},
                }
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await ptz_service.AbsoluteMove(req)
            elif move_mode == GOTOPRESET_MOVE:
                # Guard against unsupported operation
                if not profile.ptz or not profile.ptz.presets:
                    LOGGER.warning(
                        "Absolute Presets not supported on device '%s'", self.name
                    )
                    return
                if preset_val not in profile.ptz.presets:
                    LOGGER.warning(
                        (
                            "PTZ preset '%s' does not exist on device '%s'. Available"
                            " Presets: %s"
                        ),
                        preset_val,
                        self.name,
                        ", ".join(profile.ptz.presets),
                    )
                    return

                req.PresetToken = preset_val
                req.Speed = {
                    "PanTilt": {"x": speed_val, "y": speed_val},
                    "Zoom": {"x": speed_val},
                }
                await ptz_service.GotoPreset(req)
            elif move_mode == STOP_MOVE:
                await ptz_service.Stop(req)
        except ONVIFError as err:
            if "Bad Request" in err.reason:
                LOGGER.warning("Device '%s' doesn't support PTZ", self.name)
            else:
                LOGGER.error("Error trying to perform PTZ action: %s", err)

    async def async_run_aux_command(
        self,
        profile: Profile,
        cmd: str,
    ) -> None:
        """Execute a PTZ auxiliary command on the camera."""
        if not self.capabilities.ptz:
            LOGGER.warning("PTZ actions are not supported on device '%s'", self.name)
            return

        ptz_service = await self.device.create_ptz_service()

        LOGGER.debug(
            "Running Aux Command | Cmd = %s",
            cmd,
        )
        try:
            req = ptz_service.create_type("SendAuxiliaryCommand")
            req.ProfileToken = profile.token
            req.AuxiliaryData = cmd
            await ptz_service.SendAuxiliaryCommand(req)
        except ONVIFError as err:
            if "Bad Request" in err.reason:
                LOGGER.warning("Device '%s' doesn't support PTZ", self.name)
            else:
                LOGGER.error("Error trying to send PTZ auxiliary command: %s", err)

    async def async_set_imaging_settings(
        self,
        profile: Profile,
        settings: dict,
    ) -> None:
        """Set an imaging setting on the ONVIF imaging service."""
        # The Imaging Service is defined by ONVIF standard
        # https://www.onvif.org/specs/srv/img/ONVIF-Imaging-Service-Spec-v210.pdf
        if not self.capabilities.imaging:
            LOGGER.warning(
                "The imaging service is not supported on device '%s'", self.name
            )
            return

        imaging_service = await self.device.create_imaging_service()

        LOGGER.debug("Setting Imaging Setting | Settings = %s", settings)
        try:
            req = imaging_service.create_type("SetImagingSettings")
            req.VideoSourceToken = profile.video_source_token
            req.ImagingSettings = settings
            await imaging_service.SetImagingSettings(req)
        except ONVIFError as err:
            if "Bad Request" in err.reason:
                LOGGER.warning(
                    "Device '%s' doesn't support the Imaging Service", self.name
                )
            else:
                LOGGER.error("Error trying to set Imaging settings: %s", err)


def get_device(
    hass: HomeAssistant,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
) -> ONVIFCamera:
    """Get ONVIFCamera instance."""
    return ONVIFCamera(
        host,
        port,
        username,
        password,
        f"{os.path.dirname(onvif.__file__)}/wsdl/",
        no_cache=True,
    )
