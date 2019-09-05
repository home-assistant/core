"""Support for Rain Bird Irrigation system LNK WiFi Module."""

import logging

from pyrainbird import RainbirdController
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SWITCHES,
    CONF_TRIGGER_TIME,
    CONF_ZONE,
)
from homeassistant.helpers import config_validation as cv

from . import DATA_RAINBIRD, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"

SERVICE_START_IRRIGATION = "start_irrigation"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SWITCHES, default={}): vol.Schema(
            {
                cv.string: {
                    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
                    vol.Required(CONF_ZONE): cv.string,
                    vol.Required(CONF_TRIGGER_TIME): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL): cv.string,
                }
            }
        )
    }
)

SERVICE_SCHEMA_IRRIGATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Rain Bird switches over a Rain Bird controller."""
    controller = hass.data[DATA_RAINBIRD]

    devices = []
    for dev_id, switch in config.get(CONF_SWITCHES).items():
        devices.append(RainBirdSwitch(controller, switch, dev_id))
    add_entities(devices, True)

    def start_irrigation(service):
        """Set the duration device state attribute and start the irrigation."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        duration = service.data.get(ATTR_DURATION)

        for device in devices:
            if isinstance(device, RainBirdSwitch) and device.entity_id == entity_id:
                device.start_irrigation(duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_IRRIGATION,
        start_irrigation,
        schema=SERVICE_SCHEMA_IRRIGATION,
    )


class RainBirdSwitch(SwitchDevice):
    """Representation of a Rain Bird switch."""

    def __init__(self, rb: RainbirdController, dev, dev_id):
        """Initialize a Rain Bird Switch Device."""
        self._rainbird = rb
        self._devid = dev_id
        self._zone = int(dev.get(CONF_ZONE))
        self._name = dev.get(CONF_FRIENDLY_NAME, f"Sprinkler {self._zone}")
        self._state = None
        self._duration = dev.get(CONF_TRIGGER_TIME)
        self._attributes = {"duration": self._duration, "zone": self._zone}

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.start_irrigation(self._duration)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._rainbird.stop_irrigation():
            self._state = False

    def start_irrigation(self, duration: int):
        """Turn the irrigation on."""
        if self._rainbird.irrigate_zone(int(self._zone), duration):
            self._state = True

    def update(self):
        """Update switch status."""
        self._state = self._rainbird.zone_state(self._zone)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
