"""Support for exposing NX584 elements as sensors."""
from __future__ import annotations

import logging
import threading
import time

from nx584 import client as nx584_client
import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE_ZONES = "exclude_zones"
CONF_ZONE_TYPES = "zone_types"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "5007"
DEFAULT_SSL = False

ZONE_TYPES_SCHEMA = vol.Schema({cv.positive_int: BINARY_SENSOR_DEVICE_CLASSES_SCHEMA})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_EXCLUDE_ZONES, default=[]): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ZONE_TYPES, default={}): ZONE_TYPES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NX584 binary sensor platform."""

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    exclude = config[CONF_EXCLUDE_ZONES]
    zone_types = config[CONF_ZONE_TYPES]

    try:
        client = nx584_client.Client(f"http://{host}:{port}")
        zones = client.list_zones()
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NX584: %s", str(ex))
        return

    version = [int(v) for v in client.get_version().split(".")]
    if version < [1, 1]:
        _LOGGER.error("NX584 is too old to use for sensors (>=0.2 required)")
        return

    zone_sensors = {
        zone["number"]: NX584ZoneSensor(
            zone, zone_types.get(zone["number"], BinarySensorDeviceClass.OPENING)
        )
        for zone in zones
        if zone["number"] not in exclude
    }
    if zone_sensors:
        add_entities(zone_sensors.values())
        watcher = NX584Watcher(client, zone_sensors)
        watcher.start()
    else:
        _LOGGER.warning("No zones found on NX584")


class NX584ZoneSensor(BinarySensorEntity):
    """Representation of a NX584 zone as a sensor."""

    def __init__(self, zone, zone_type):
        """Initialize the nx594 binary sensor."""
        self._zone = zone
        self._zone_type = zone_type

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._zone["name"]

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # True means "faulted" or "open" or "abnormal state"
        return self._zone["state"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "zone_number": self._zone["number"],
            "bypassed": self._zone.get("bypassed", False),
        }


class NX584Watcher(threading.Thread):
    """Event listener thread to process NX584 events."""

    def __init__(self, client, zone_sensors):
        """Initialize NX584 watcher thread."""
        super().__init__()
        self.daemon = True
        self._client = client
        self._zone_sensors = zone_sensors

    def _process_zone_event(self, event):
        zone = event["zone"]
        # pylint: disable=protected-access
        if not (zone_sensor := self._zone_sensors.get(zone)):
            return
        zone_sensor._zone["state"] = event["zone_state"]
        zone_sensor.schedule_update_ha_state()

    def _process_events(self, events):
        for event in events:
            if event.get("type") == "zone_status":
                self._process_zone_event(event)

    def _run(self):
        """Throw away any existing events so we don't replay history."""
        self._client.get_events()
        while True:
            if events := self._client.get_events():
                self._process_events(events)

    def run(self):
        """Run the watcher."""
        while True:
            try:
                self._run()
            except requests.exceptions.ConnectionError:
                _LOGGER.error("Failed to reach NX584 server")
                time.sleep(10)
