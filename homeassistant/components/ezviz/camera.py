"""Support ezviz camera devices."""

import logging
from typing import override

import aiohttp
from pyezvizapi.exceptions import HTTPError, InvalidHost, PyEzvizError
from pyezvizapi.utils import decrypt_image

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.stream import CONF_USE_WALLCLOCK_AS_TIMESTAMPS
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)

from .const import (
    ATTR_SERIAL,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_CAMERA_USERNAME,
    DEFAULT_FFMPEG_ARGUMENTS,
    DOMAIN,
    SERVICE_WAKE_DEVICE,
)
from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity
from .vtm import async_register_vtm_camera, rtsp_available, vtm_stream_url

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ cameras based on a config entry."""

    coordinator = entry.runtime_data

    camera_entities = []

    for camera, value in coordinator.data.items():
        camera_rtsp_entry = [
            item
            for item in hass.config_entries.async_entries(DOMAIN)
            if item.unique_id == camera and item.source != SOURCE_IGNORE
        ]

        if camera_rtsp_entry:
            ffmpeg_arguments = camera_rtsp_entry[0].options[CONF_FFMPEG_ARGUMENTS]
            camera_username = camera_rtsp_entry[0].data[CONF_USERNAME]
            camera_password = camera_rtsp_entry[0].data[CONF_PASSWORD]

            camera_rtsp_stream = f"rtsp://{camera_username}:{camera_password}@{value['local_ip']}:{value['local_rtsp_port']}{ffmpeg_arguments}"
            _LOGGER.debug(
                "Configuring Camera %s with ip: %s rtsp port: %s ffmpeg arguments: %s",
                camera,
                value["local_ip"],
                value["local_rtsp_port"],
                ffmpeg_arguments,
            )

        elif rtsp_available(value):
            discovery_flow.async_create_flow(
                hass,
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={
                    ATTR_SERIAL: camera,
                    CONF_IP_ADDRESS: value["local_ip"],
                },
            )

            _LOGGER.warning(
                (
                    "Found camera with serial %s without configuration. Please go to"
                    " integration to complete setup"
                ),
                camera,
            )

            ffmpeg_arguments = DEFAULT_FFMPEG_ARGUMENTS
            camera_username = DEFAULT_CAMERA_USERNAME
            camera_password = None
            camera_rtsp_stream = ""

        else:
            # No RTSP on the device: live view goes through the VTM cloud relay,
            # which needs no camera credentials.
            ffmpeg_arguments = DEFAULT_FFMPEG_ARGUMENTS
            camera_username = DEFAULT_CAMERA_USERNAME
            camera_password = None
            camera_rtsp_stream = None

        use_vtm = camera_password is None or not rtsp_available(value)
        if use_vtm:
            async_register_vtm_camera(hass, entry, camera, coordinator.ezviz_client)

        camera_entities.append(
            EzvizCamera(
                hass,
                coordinator,
                camera,
                camera_username,
                camera_password,
                camera_rtsp_stream,
                value["local_rtsp_port"],
                ffmpeg_arguments,
                use_vtm,
            )
        )

    async_add_entities(camera_entities)

    platform = async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_WAKE_DEVICE, None, "perform_wake_device"
    )


class EzvizCamera(EzvizEntity, Camera):
    """An implementation of a EZVIZ security camera."""

    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        camera_username: str,
        camera_password: str | None,
        camera_rtsp_stream: str | None,
        local_rtsp_port: int,
        ffmpeg_arguments: str | None,
        use_vtm: bool,
    ) -> None:
        """Initialize a EZVIZ security camera."""
        super().__init__(coordinator, serial)
        Camera.__init__(self)
        self.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = True
        self._username = camera_username
        self._password = camera_password
        self._rtsp_stream = camera_rtsp_stream
        self._local_rtsp_port = local_rtsp_port
        self._ffmpeg_arguments = ffmpeg_arguments
        self._ffmpeg = get_ffmpeg_manager(hass)
        self._attr_unique_id = serial
        self._use_vtm = use_vtm
        if camera_password or use_vtm:
            self._attr_supported_features = CameraEntityFeature.STREAM

    @property
    @override
    def is_on(self) -> bool:
        """Return true if on."""
        return bool(self.data["status"])

    @property
    @override
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.data["alarm_notify"]

    @property
    @override
    def motion_detection_enabled(self) -> bool:
        """Camera Motion Detection Status."""
        return self.data["alarm_notify"]

    @override
    def enable_motion_detection(self) -> None:
        """Enable motion detection in camera."""
        try:
            self.coordinator.ezviz_client.set_camera_defence(self._serial, 1)

        except InvalidHost as err:
            raise InvalidHost("Error enabling motion detection") from err

    @override
    def disable_motion_detection(self) -> None:
        """Disable motion detection."""
        try:
            self.coordinator.ezviz_client.set_camera_defence(self._serial, 0)

        except InvalidHost as err:
            raise InvalidHost("Error disabling motion detection") from err

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a frame from the camera stream."""
        if self._use_vtm:
            return await self._async_vtm_camera_image(width, height)
        if self._rtsp_stream is None:
            return None
        return await ffmpeg.async_get_image(
            self.hass, self._rtsp_stream, width=width, height=height
        )

    async def _async_vtm_camera_image(
        self, width: int | None, height: int | None
    ) -> bytes | None:
        """Return a still image without waking a sleeping device.

        Opening the relay just for a snapshot would wake battery devices on
        every dashboard refresh, so use the stream only while it has active
        outputs (async_get_image would restart a stopped one) and the last
        alarm picture otherwise.
        """
        if (
            self.stream is not None
            and self.stream.outputs()
            and (image := await self.stream.async_get_image(width, height))
        ):
            return image

        url = self.data.get("last_alarm_pic")
        if not isinstance(url, str) or not url:
            return None
        try:
            response = await async_get_clientsession(self.hass).get(url)
            response.raise_for_status()
            image = await response.read()
        except aiohttp.ClientError as err:
            _LOGGER.debug("%s: cannot fetch last alarm picture: %s", self._serial, err)
            return None
        if self.data.get("encrypted") and self._password is not None:
            try:
                image = decrypt_image(image, self._password)
            except PyEzvizError:
                _LOGGER.debug("%s: cannot decrypt last alarm picture", self._serial)
        return image

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source."""
        if self._use_vtm:
            return vtm_stream_url(self.hass, self._serial)
        if self._password is None:
            return None
        local_ip = self.data["local_ip"]
        self._rtsp_stream = (
            f"rtsp://{self._username}:{self._password}@"
            f"{local_ip}:{self._local_rtsp_port}{self._ffmpeg_arguments}"
        )
        _LOGGER.debug(
            "Configuring Camera %s with ip: %s rtsp port: %s ffmpeg arguments: %s",
            self._serial,
            local_ip,
            self._local_rtsp_port,
            self._ffmpeg_arguments,
        )

        return self._rtsp_stream

    def perform_wake_device(self) -> None:
        """Basically wakes the camera by querying the device."""
        try:
            self.coordinator.ezviz_client.get_detection_sensibility(self._serial)
        except (HTTPError, PyEzvizError) as err:
            raise PyEzvizError("Cannot wake device") from err
