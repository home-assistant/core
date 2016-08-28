"""
Support for Insteon Hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
import logging

from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config, discovery
from homeassistant.helpers.entity import Entity

DOMAIN = 'insteon_hub'  # type: str
REQUIREMENTS = ['insteon_hub==0.5.0']  # type: list
INSTEON = None  # type: Insteon
DEVCAT = 'DevCat'  # type: str
SUBCAT = 'SubCat'  # type: str
DEVICE_CLASSES = ['light', 'fan']  # type: list

_LOGGER = logging.getLogger(__name__)


def _is_successful(response: dict) -> bool:
    """Check http response for successful status."""
    return 'status' in response and response['status'] == 'succeeded'


def filter_devices(devices: list, categories: list) -> list:
    """Filter insteon device list by category/subcategory."""
    categories = (categories
                  if isinstance(categories, list)
                  else [categories])
    matching_devices = []
    for device in devices:
        if any(
                device.DevCat == c[DEVCAT] and
                (SUBCAT not in c or device.SubCat in c[SUBCAT])
                for c in categories):
            matching_devices.append(device)
    return matching_devices


def setup(hass, config: dict) -> bool:
    """Setup Insteon Hub component."""
    if not validate_config(
            config,
            {DOMAIN: [CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY]},
            _LOGGER):
        return False

    from insteon import Insteon

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    api_key = config[DOMAIN][CONF_API_KEY]

    global INSTEON
    INSTEON = Insteon(username, password, api_key)

    if INSTEON is None:
        _LOGGER.error('Could not connect to Insteon service.')
        return

    for device_class in DEVICE_CLASSES:
        discovery.load_platform(hass, device_class, DOMAIN, {}, config)
    return True


class InsteonDevice(Entity):
    """Represents an insteon device."""

    def __init__(self: Entity, node: object) -> None:
        """Initialize the insteon device."""
        self._node = node

    def update(self: Entity) -> None:
        """Update state of the device."""
        pass

    @property
    def name(self: Entity) -> str:
        """Name of the insteon device."""
        return self._node.DeviceName

    @property
    def unique_id(self: Entity) -> str:
        """Unique identifier for the device."""
        return self._node.DeviceID

    @property
    def supported_features(self: Entity) -> int:
        """Supported feature flags."""
        return 0

    def _send_command(self: Entity, command: str, level: int=None,
                      payload: dict=None) -> bool:
        """Send command to insteon device."""
        resp = self._node.send_command(command, payload=payload, level=level,
                                       wait=True)
        return _is_successful(resp)
