"""Support for Rain Bird Irrigation system LNK WiFi Module."""

import logging

from pyrainbird import AvailableStations, RainbirdController
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TRIGGER_TIME,
    CONF_ZONE,
)
from homeassistant.helpers import config_validation as cv

from . import DATA_RAINBIRD, DOMAIN, RAINBIRD_CONTROLLER

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"

SERVICE_START_IRRIGATION = "start_irrigation"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(RAINBIRD_CONTROLLER): cv.string,
        vol.Required(CONF_ZONE): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.string,
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

    if discovery_info is None:
        return False

    controller: RainbirdController = hass.data[DATA_RAINBIRD][
        discovery_info[RAINBIRD_CONTROLLER]
    ]
    available_stations: AvailableStations = controller.get_available_stations()
    devices = []
    for i in range(1, available_stations.stations.count + 1):
        if available_stations.stations.active(i):
            time = discovery_info.get("zones", {}).get(
                CONF_TRIGGER_TIME, discovery_info.get(CONF_TRIGGER_TIME, 0)
            )
            name = discovery_info.get("zones", {}).get(CONF_FRIENDLY_NAME)
            if time:
                devices.append(RainBirdSwitch(controller, i, time, name=name))
            else:
                logging.warning(
                    "No delay configured for zone {0:d}, controller {1:s}. "
                    "Not adding sprinklers for zone {0:d}.".format(
                        i, discovery_info[RAINBIRD_CONTROLLER]
                    )
                )

    add_entities(devices, True)

    def _start_irrigation(service):
        entity_id = service.data.get(ATTR_ENTITY_ID)
        duration = service.data.get(ATTR_DURATION)

        for d in devices:
            if d.entity_id == entity_id:
                d.turn_on(duration=duration)

    hass.services.register(
        DOMAIN,
        SERVICE_START_IRRIGATION,
        _start_irrigation,
        schema=SERVICE_SCHEMA_IRRIGATION,
    )


class RainBirdSwitch(SwitchDevice):
    """Representation of a Rain Bird switch."""

    def __init__(self, controller: RainbirdController, zone, time, name=None):
        """Initialize a Rain Bird Switch Device."""
        self._rainbird = rb
        self._zone = int(dev.get(CONF_ZONE))
        self._name = dev.get(CONF_FRIENDLY_NAME, f"Sprinkler {self._zone}")
        self._state = None
        self._duration = time
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
        if self._rainbird.irrigate_zone(
            int(self._zone),
            kwargs["duration"] if "duration" in kwargs else self._duration,
        ):
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._rainbird.stop_irrigation():
            self._state = False

    def update(self):
        """Update switch status."""
        self._state = self._rainbird.zone_state(self._zone)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
