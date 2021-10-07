"""Support for Hydrawise cloud switches."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    PLATFORM_SCHEMA,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DATA_HYDRAWISE,
    DEFAULT_WATERING_TIME,
    HydrawiseEntity,
)

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        name="Automatic Watering",
        device_class=DEVICE_CLASS_SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        name="Manual Watering",
        device_class=DEVICE_CLASS_SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SWITCH_KEYS): vol.All(
            cv.ensure_list, [vol.In(SWITCH_KEYS)]
        ),
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME): vol.All(
            vol.In(ALLOWED_WATERING_TIME)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    default_watering_timer = config[CONF_WATERING_TIME]

    entities = [
        HydrawiseSwitch(zone, description, default_watering_timer)
        for zone in hydrawise.relays
        for description in SWITCH_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self, data, description: SwitchEntityDescription, default_watering_timer
    ):
        """Initialize a switch for Hydrawise device."""
        super().__init__(data, description)
        self._default_watering_timer = default_watering_timer

    def turn_on(self, **kwargs):
        """Turn the device on."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(
                self._default_watering_timer, relay_data
            )
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(0, relay_data)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        relay_data = self.data["relay"] - 1
        if self.entity_description.key == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(0, relay_data)
        elif self.entity_description.key == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(365, relay_data)

    def update(self):
        """Update device state."""
        relay_data = self.data["relay"] - 1
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise switch: %s", self.name)
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = mydata.relays[relay_data]["timestr"] == "Now"
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = (mydata.relays[relay_data]["timestr"] != "") and (
                mydata.relays[relay_data]["timestr"] != "Now"
            )
