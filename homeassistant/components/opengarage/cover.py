"""Platform for the opengarage.io cover component."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverDevice,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE_SENSOR = "distance_sensor"
ATTR_DOOR_STATE = "door_state"
ATTR_SIGNAL_STRENGTH = "wifi_signal"

CONF_DEVICE_KEY = "device_key"

DEFAULT_NAME = "OpenGarage"
DEFAULT_PORT = 80

STATES_MAP = {0: STATE_CLOSED, 1: STATE_OPEN}

COVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the OpenGarage covers."""
    covers = []
    devices = config.get(CONF_COVERS)

    for device_config in devices.values():
        args = {
            CONF_NAME: device_config.get(CONF_NAME),
            CONF_HOST: device_config.get(CONF_HOST),
            CONF_PORT: device_config.get(CONF_PORT),
            CONF_SSL: device_config.get(CONF_SSL),
            CONF_VERIFY_SSL: device_config.get(CONF_VERIFY_SSL),
            CONF_DEVICE_KEY: device_config.get(CONF_DEVICE_KEY),
        }

        covers.append(OpenGarageCover(args))

    add_entities(covers, True)


class OpenGarageCover(CoverDevice):
    """Representation of a OpenGarage cover."""

    def __init__(self, args):
        """Initialize the cover."""
        self.opengarage_url = (
            f"http{'s' if args[CONF_SSL] else ''}://"
            f"{args[CONF_HOST]}:{args[CONF_PORT]}"
        )
        self._name = args[CONF_NAME]
        self._device_key = args[CONF_DEVICE_KEY]
        self._state = None
        self._state_before_move = None
        self._device_state_attributes = {}
        self._available = True
        self._verify_ssl = args[CONF_VERIFY_SSL]

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._device_state_attributes

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state in [STATE_CLOSED, STATE_OPENING]

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._state in [STATE_CLOSED, STATE_CLOSING]:
            return
        self._state_before_move = self._state
        self._state = STATE_CLOSING
        self._push_button()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self._state in [STATE_OPEN, STATE_OPENING]:
            return
        self._state_before_move = self._state
        self._state = STATE_OPENING
        self._push_button()

    def update(self):
        """Get updated status from API."""
        try:
            status = requests.get(f"{self.opengarage_url}/jc", timeout=10).json()
        except requests.exceptions.RequestException as ex:
            _LOGGER.error(
                "Unable to connect to OpenGarage device: %(reason)s", dict(reason=ex)
            )
            self._available = False
            return

        if self._name is None and status["name"] is not None:
            self._name = status["name"]
        state = STATES_MAP.get(status.get("door"))
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

        _LOGGER.debug("%s status: %s", self._name, self._state)
        if status.get("rssi") is not None:
            self._device_state_attributes[ATTR_SIGNAL_STRENGTH] = status.get("rssi")
        if status.get("dist") is not None:
            self._device_state_attributes[ATTR_DISTANCE_SENSOR] = status.get("dist")
        if self._state is not None:
            self._device_state_attributes[ATTR_DOOR_STATE] = self._state

        self._available = True

    def _push_button(self):
        """Send commands to API."""
        result = -1
        try:
            result = requests.get(
                f"{self.opengarage_url}/cc?dkey={self._device_key}&click=1",
                timeout=10,
                verify=self._verify_ssl,
            ).json()["result"]
        except requests.exceptions.RequestException as ex:
            _LOGGER.error(
                "Unable to connect to OpenGarage device: %(reason)s", dict(reason=ex)
            )
        if result == 1:
            return

        if result == 2:
            _LOGGER.error("Unable to control %s: Device key is incorrect", self._name)
        elif result > 2:
            _LOGGER.error("Unable to control %s: Error code %s", self._name, result)

        self._state = self._state_before_move
        self._state_before_move = None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE
