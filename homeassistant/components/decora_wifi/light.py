"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

import logging

# pylint: disable=import-error
from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

NOTIFICATION_ID = "leviton_notification"
NOTIFICATION_TITLE = "myLeviton Decora Setup"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Decora WiFi platform."""

    email = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    session = DecoraWiFiSession()

    try:
        success = session.login(email, password)

        # If login failed, notify user.
        if success is None:
            msg = "Failed to log into myLeviton Services. Check credentials."
            _LOGGER.error(msg)
            hass.components.persistent_notification.create(
                msg, title=NOTIFICATION_TITLE, notification_id=NOTIFICATION_ID
            )
            return False

        # Gather all the available devices...
        perms = session.user.get_residential_permissions()
        all_switches = []
        for permission in perms:
            if permission.residentialAccountId is not None:
                acct = ResidentialAccount(session, permission.residentialAccountId)
                for residence in acct.get_residences():
                    for switch in residence.get_iot_switches():
                        all_switches.append(switch)
            elif permission.residenceId is not None:
                residence = Residence(session, permission.residenceId)
                for switch in residence.get_iot_switches():
                    all_switches.append(switch)

        add_entities(DecoraWifiLight(sw) for sw in all_switches)
    except ValueError:
        _LOGGER.error("Failed to communicate with myLeviton Service.")

    # Listen for the stop event and log out.
    def logout(event):
        """Log out..."""
        try:
            if session is not None:
                Person.logout(session)
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service.")

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)


class DecoraWifiLight(LightEntity):
    """Representation of a Decora WiFi switch."""

    def __init__(self, switch):
        """Initialize the switch."""
        self._switch = switch

    @property
    def supported_features(self):
        """Return supported features."""
        if self._switch.canSetLevel:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        return 0

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def brightness(self):
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.power == "ON"

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on & adjust brightness."""
        attribs = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            min_level = self._switch.data.get("minLevel", 0)
            max_level = self._switch.data.get("maxLevel", 100)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * max_level / 255)
            brightness = max(brightness, min_level)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION])
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch.")

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}
        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch.")

    def update(self):
        """Fetch new state data for this switch."""
        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data.")
