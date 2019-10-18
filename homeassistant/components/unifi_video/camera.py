"""Support for Ubiquiti's Unifi Video cameras."""
import logging

from unifi_video import UnifiVideoAPI
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_API_KEY = "api_key"
CONF_VERIFY_CERT = "verify_cert"

DEFAULT_PORT = 7443
DEFAULT_SSL = True
DEFAULT_VERIFY_CERT = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_CERT, default=DEFAULT_VERIFY_CERT): cv.boolean,
    }
)


class UnifiVideoError(HomeAssistantError):
    """General Unifi Video exception."""


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Discover cameras on a Unifi Video."""
    host = config[CONF_HOST]
    api_key = config[CONF_API_KEY]
    port = config[CONF_PORT]
    ssl = config[CONF_SSL]
    verify_cert = config[CONF_VERIFY_CERT]

    try:
        uva = UnifiVideoAPI(
            api_key=api_key,
            addr=host,
            port=port,
            schema="https" if ssl else "http",
            verify_cert=verify_cert,
            check_ufv_version=False,
        )
    except Exception as exception:
        raise UnifiVideoError(f"Unifi platform setup error: {exception}")

    _LOGGER.info(
        "Connected to %s v%s", uva._name, uva._version
    )  # pylint: disable=W0212

    add_entities([UnifiVideoCamera(camera) for camera in uva.cameras])


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, camera):
        """Initialize a Unifi camera."""
        super().__init__()
        self._camera = camera
        self.is_streaming = False

    def update(self):
        """Update camera data."""
        self._camera.update()

    @property
    def name(self):
        """Return the name of the camera."""
        return self._camera.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._camera._data["recordingSettings"][
            "fullTimeRecordEnabled"
        ]  # pylint: disable=W0212

    @property
    def brand(self):
        """Return the brand of this camera."""
        return "Ubiquiti"

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._camera._data["recordingSettings"][
            "motionRecordEnabled"
        ]  # pylint: disable=W0212

    @property
    def model(self):
        """Return the camera model."""
        return self._camera.model

    def camera_image(self):
        """Return bytes of camera image."""
        return self._camera.snapshot(True, width=1280)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        try:
            success = self._camera.set_recording_settings(recording_mode="motion")
            if not success:
                raise UnifiVideoError("Enabling motion detection unsuccessfull")
        except Exception:
            raise UnifiVideoError(
                "Failed to enable motion detection, check permission and version compatibility"
            )

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        try:
            success = self._camera.set_recording_settings(recording_mode="disable")
            if not success:
                raise UnifiVideoError("Disabling motion detection unsuccessfull")
        except Exception:
            raise UnifiVideoError(
                "Failed to disable motion detection, check permission and version compatibility"
            )
