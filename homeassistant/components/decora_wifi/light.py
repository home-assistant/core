"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

from __future__ import annotations

import logging
from typing import Any

from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DecoraComponentData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

NOTIFICATION_ID = "leviton_notification"
NOTIFICATION_TITLE = "myLeviton Decora Setup"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Will write later."""

    component: DecoraComponentData = hass.data[DOMAIN][entry.entry_id]

    try:
        session = component.session
        assert session.user

        perms = await hass.async_add_executor_job(
            session.user.get_residential_permissions
        )
        residences: list[Residence] = []
        for permission in perms:
            if permission.residentialAccountId is not None:
                account = ResidentialAccount(session, permission.residentialAccountId)
                residences.extend(
                    await hass.async_add_executor_job(account.get_residences)
                )
            elif permission.residenceId is not None:
                residences.append(Residence(session, permission.residenceId))

        switches = [
            sw
            for res in residences
            for sw in (await hass.async_add_executor_job(res.get_iot_switches))
        ]

        async_add_entities([DecoraWifiLight(sw) for sw in switches])

    except ValueError:
        _LOGGER.error("Failed to communicate with myLeviton Service")


class DecoraWifiLight(LightEntity):
    """Representation of a Decora WiFi switch."""

    def __init__(self, switch) -> None:
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
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def unique_id(self) -> str:
        """Return the ID of this light."""
        return self._switch.serial

    @property
    def brightness(self) -> int:
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self) -> bool:
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer=self._switch.manufacturer,
            model=self._switch.model,
            sw_version=self._switch.version,
            serial_number=self._switch.serial,
        )
