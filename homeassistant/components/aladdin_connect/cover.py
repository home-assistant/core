"""Platform for the Aladdin Connect cover component."""
import logging

from aladdin_connect import AladdinConnectClient
import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "aladdin_notification"
NOTIFICATION_TITLE = "Aladdin Connect Cover Setup"

STATES_MAP = {
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
}

SUPPORTED_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Aladdin Connect platform."""

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    acc = AladdinConnectClient(username, password)

    try:
        if not acc.login():
            raise ValueError("Username or Password is incorrect")
        add_entities(AladdinDevice(acc, door) for door in acc.get_doors())
    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            "Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )


class AladdinDevice(CoverEntity):
    """Representation of Aladdin Connect cover."""

    def __init__(self, acc, device):
        """Initialize the cover."""
        self._acc = acc
        self._device_id = device["device_id"]
        self._number = device["door_number"]
        self._name = device["name"]
        self._status = STATES_MAP.get(device["status"])

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return "garage"

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device_id}-{self._number}"

    @property
    def name(self):
        """Return the name of the garage door."""
        return self._name

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._status == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._status == STATE_CLOSING

    @property
    def is_closed(self):
        """Return None if status is unknown, True if closed, else False."""
        if self._status is None:
            return None
        return self._status == STATE_CLOSED

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self._acc.close_door(self._device_id, self._number)

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self._acc.open_door(self._device_id, self._number)

    def update(self):
        """Update status of cover."""
        acc_status = self._acc.get_door_status(self._device_id, self._number)
        self._status = STATES_MAP.get(acc_status)
