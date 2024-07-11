"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

from __future__ import annotations

import logging
from typing import Any

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

NOTIFICATION_ID = "leviton_notification"
NOTIFICATION_TITLE = "myLeviton Decora Setup"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
            persistent_notification.create(
                hass, msg, title=NOTIFICATION_TITLE, notification_id=NOTIFICATION_ID
            )
            return

        # Gather all the available devices...
        perms = session.user.get_residential_permissions()
        all_switches: list = []
        for permission in perms:
            if permission.residentialAccountId is not None:
                acct = ResidentialAccount(session, permission.residentialAccountId)
                all_switches.extend(
                    switch
                    for residence in acct.get_residences()
                    for switch in residence.get_iot_switches()
                )
            elif permission.residenceId is not None:
                residence = Residence(session, permission.residenceId)
                all_switches.extend(residence.get_iot_switches())

        add_entities(DecoraWifiLight(sw) for sw in all_switches)
    except ValueError:
        _LOGGER.error("Failed to communicate with myLeviton Service")

    # Listen for the stop event and log out.
    def logout(event):
        """Log out..."""
        try:
            if session is not None:
                Person.logout(session)
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service")

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)


class DecoraWifiLight(LightEntity):
    """Representation of a Decora WiFi switch."""

    def __init__(self, switch):
        """Initialize the switch."""
        self._switch = switch
        self._attr_unique_id = switch.serial

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        if self._switch.canSetLevel:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        if self._switch.canSetLevel:
            return LightEntityFeature.TRANSITION
        return LightEntityFeature(0)

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._switch.serial

    @property
    def brightness(self):
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.power == "ON"

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on & adjust brightness."""
        attribs: dict[str, Any] = {"power": "ON"}

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
            _LOGGER.error("Failed to turn on myLeviton switch")

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}
        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    def update(self) -> None:
        """Fetch new state data for this switch."""
        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
