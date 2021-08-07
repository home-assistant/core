"""Support for Brunt Blind Engine covers."""
from __future__ import annotations

import logging

from brunt import BruntAPI
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_WINDOW,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

ATTR_REQUEST_POSITION = "request_position"
NOTIFICATION_ID = "brunt_notification"
NOTIFICATION_TITLE = "Brunt Cover Setup"
ATTRIBUTION = "Based on an unofficial Brunt SDK."

CLOSED_POSITION = 0
OPEN_POSITION = 100

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the brunt platform."""

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    bapi = BruntAPI(username=username, password=password)
    try:
        things = bapi.getThings()["things"]
        if not things:
            _LOGGER.error("No things present in account")
        else:
            add_entities(
                [
                    BruntDevice(bapi, thing["NAME"], thing["thingUri"])
                    for thing in things
                ],
                True,
            )
    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            "Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )


class BruntDevice(CoverEntity):
    """
    Representation of a Brunt cover device.

    Contains the common logic for all Brunt devices.
    """

    _attr_device_class = DEVICE_CLASS_WINDOW
    _attr_supported_features = COVER_FEATURES

    def __init__(self, bapi, name, thing_uri):
        """Init the Brunt device."""
        self._bapi = bapi
        self._attr_name = name
        self._thing_uri = thing_uri

        self._state = {}

    @property
    def request_cover_position(self) -> int | None:
        """
        Return request position of cover.

        The request position is the position of the last request
        to Brunt, at times there is a diff of 1 to current
        None is unknown, 0 is closed, 100 is fully open.
        """
        pos = self._state.get("requestPosition")
        return int(pos) if pos else None

    @property
    def move_state(self) -> int | None:
        """
        Return current moving state of cover.

        None is unknown, 0 when stopped, 1 when opening, 2 when closing
        """
        mov = self._state.get("moveState")
        return int(mov) if mov else None

    def update(self):
        """Poll the current state of the device."""
        try:
            self._state = self._bapi.getState(thingUri=self._thing_uri).get("thing")
            self._attr_available = True
        except (TypeError, KeyError, NameError, ValueError) as ex:
            _LOGGER.error("%s", ex)
            self._attr_available = False
        self._attr_is_opening = self.move_state == 1
        self._attr_is_closing = self.move_state == 2
        pos = self._state.get("currentPosition")
        self._attr_current_cover_position = int(pos) if pos else None
        self._attr_is_closed = self.current_cover_position == CLOSED_POSITION
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_REQUEST_POSITION: self.request_cover_position,
        }

    def open_cover(self, **kwargs):
        """Set the cover to the open position."""
        self._bapi.changeRequestPosition(OPEN_POSITION, thingUri=self._thing_uri)

    def close_cover(self, **kwargs):
        """Set the cover to the closed position."""
        self._bapi.changeRequestPosition(CLOSED_POSITION, thingUri=self._thing_uri)

    def set_cover_position(self, **kwargs):
        """Set the cover to a specific position."""
        self._bapi.changeRequestPosition(
            kwargs[ATTR_POSITION], thingUri=self._thing_uri
        )
