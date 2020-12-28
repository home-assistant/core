"""Support for SwitchBot curtains."""
from typing import Any, Dict

# pylint: disable=import-error, no-member
import switchbot
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_CURTAIN,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

CLOSED_POSITION = 0
OPEN_POSITION = 100

DEFAULT_NAME = "Switchbot Curtain"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Switchbot devices."""
    name = config.get(CONF_NAME)
    mac_addr = config[CONF_MAC]
    password = config.get(CONF_PASSWORD)
    add_entities([SwitchBotCurtain(mac_addr, name, password)])


class SwitchBotCurtain(CoverEntity, RestoreEntity):
    """Representation of a Switchbot Curtain."""

    def __init__(self, mac, name, password) -> None:
        """Initialize the Switchbot Curtain."""

        self._state = None
        self._last_run_success = None
        self._position = None
        self._name = name
        self._mac = mac
        self._device = switchbot.SwitchbotCurtain(mac=mac, password=password)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            self._position = state.attributes.get("current_cover_position")
        else:
            self._state = "unknown"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def name(self):
        """Return the name of the device as reported by tellcore."""
        return self._name

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CURTAIN

    @property
    def supported_features(self):
        """Flag supported features."""
        return COVER_FEATURES

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return True

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self.current_cover_position == CLOSED_POSITION

    def open_cover(self, **kwargs):
        """Set the cover to the open position."""
        if self._device.open():
            self._state = "open"
            self._position = OPEN_POSITION
            self._last_run_success = True
        else:
            self._last_run_success = False

    def close_cover(self, **kwargs):
        """Set the cover to the closed position."""
        if self._device.close():
            self._state = "closed"
            self._position = CLOSED_POSITION
            self._last_run_success = True
        else:
            self._last_run_success = False

    def set_cover_position(self, **kwargs):
        """Set the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self._device.set_position(position):
            self._state = "open"
            self._position = position
            self._last_run_success = True
        else:
            self._last_run_success = False

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {
            "last_run_success": self._last_run_success,
            "current_cover_position": self._position,
        }
