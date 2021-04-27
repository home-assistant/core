"""Support for Technicolor routers."""
import logging
from pprint import pformat

from technicolorgateway import TechnicolorGateway
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=""): cv.string,
        vol.Optional(CONF_USERNAME, default=""): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def get_scanner(hass, config):
    """Validate the configuration and returns a Technicolor scanner."""
    info = config[DOMAIN]
    devices = info[CONF_DEVICES]
    excluded_devices = info[CONF_EXCLUDE]

    gateway = TechnicolorGateway(
        info.get(CONF_HOST), "80", info.get(CONF_USERNAME), info.get(CONF_PASSWORD)
    )
    gateway.srp6authenticate()
    scanner = TechnicolorDeviceScanner(gateway, devices, excluded_devices)

    _LOGGER.debug("Logging in")

    results = scanner._get_attached_devices()

    if results is not None:
        scanner.last_results = results
    else:
        _LOGGER.error("Failed to Login")
        return None

    return scanner


class TechnicolorDeviceScanner(DeviceScanner):
    """Queries a Technicolor wireless router using web."""

    def __init__(
        self,
        gateway,
        devices,
        excluded_devices,
    ):
        """Initialize the scanner."""
        self.gateway = gateway
        self.tracked_devices = devices
        self.excluded_devices = excluded_devices
        self.last_results = []

    def get_device_name(self, device: str) -> str:
        """Return the name of the given device or the MAC if we don't know."""
        name = None
        for dev in self.last_results:
            if dev["mac"] == device:
                name = dev["name"]
                break

        if not name or name == "--":
            name = device

        return name

    def get_extra_attributes(self, device: str) -> dict:
        """Get the extra attributes of a device."""
        return {}

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        devices = []

        for dev in self.last_results:
            tracked = (
                not self.tracked_devices
                or dev["mac"] in self.tracked_devices
                or dev["name"] in self.tracked_devices
            )
            tracked = tracked and (
                not self.excluded_devices
                or not (
                    dev["mac"] in self.excluded_devices
                    or dev["name"] in self.excluded_devices
                )
            )
            if tracked:
                devices.append(dev["mac"])

        return devices

    def _update_info(self):
        _LOGGER.debug("Scanning")

        results = self._get_attached_devices()

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Scan result: \n%s", pformat(results))

        if results is None:
            _LOGGER.warning("Error scanning devices")

        self.last_results = results or []

    def _get_attached_devices(self):
        return self.gateway.get_device_modal()
