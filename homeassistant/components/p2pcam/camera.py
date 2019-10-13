"""P2PCamera integration"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_HOST, CONF_IP_ADDRESS
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from .const import DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Register camera"""
    async_add_entities([P2PCam(hass, config)])


class P2PCam(Camera):
    """P2PCamera entity."""

    def __init__(self, hass, config):
        """Init of the P2PCamera."""
        super().__init__()
        import p2pcam as p2pcam_req

        if CONF_HOST not in config:
            config[CONF_HOST] = get_host_ip()

        self._name = config[CONF_NAME]
        self._host_ip = config[CONF_HOST]
        self._target_ip = config[CONF_IP_ADDRESS]

        self.camera = p2pcam_req.P2PCam(self._host_ip, self._target_ip)

    async def async_camera_image(self):
        """Retrieve the camera image."""
        return self.camera.retrieveImage()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name


def get_host_ip():
    """Get the host ip"""
    import socket

    return [
        l
        for l in (
            [
                ip
                for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                if not ip.startswith("127.")
            ][:1],
            [
                [
                    (s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close())
                    for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]
                ][0][1]
            ],
        )
        if l
    ][0][0]
