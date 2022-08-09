"""Support for interfacing with Monoprice Blackbird 4k 8x8 HDBaseT Matrix."""
from __future__ import annotations

import logging
import socket

from pyblackbird import get_blackbird
from serial import SerialException
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, SERVICE_SETALLZONES

_LOGGER = logging.getLogger(__name__)

MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

ZONE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

CONF_ZONES = "zones"
CONF_SOURCES = "sources"

DATA_BLACKBIRD = "blackbird"

ATTR_SOURCE = "source"

BLACKBIRD_SETALLZONES_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {vol.Required(ATTR_SOURCE): cv.string}
)


# Valid zone ids: 1-8
ZONE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

# Valid source ids: 1-8
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PORT, CONF_HOST),
    PLATFORM_SCHEMA.extend(
        {
            vol.Exclusive(CONF_PORT, CONF_TYPE): cv.string,
            vol.Exclusive(CONF_HOST, CONF_TYPE): cv.string,
            vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
            vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
        }
    ),
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Monoprice Blackbird 4k 8x8 HDBaseT Matrix platform."""
    if DATA_BLACKBIRD not in hass.data:
        hass.data[DATA_BLACKBIRD] = {}

    port = config.get(CONF_PORT)
    host = config.get(CONF_HOST)

    connection = None
    if port is not None:
        try:
            blackbird = get_blackbird(port)
            connection = port
        except SerialException:
            _LOGGER.error("Error connecting to the Blackbird controller")
            return

    if host is not None:
        try:
            blackbird = get_blackbird(host, False)
            connection = host
        except socket.timeout:
            _LOGGER.error("Error connecting to the Blackbird controller")
            return

    sources = {
        source_id: extra[CONF_NAME] for source_id, extra in config[CONF_SOURCES].items()
    }

    devices = []
    for zone_id, extra in config[CONF_ZONES].items():
        _LOGGER.info("Adding zone %d - %s", zone_id, extra[CONF_NAME])
        unique_id = f"{connection}-{zone_id}"
        device = BlackbirdZone(blackbird, sources, zone_id, extra[CONF_NAME])
        hass.data[DATA_BLACKBIRD][unique_id] = device
        devices.append(device)

    add_entities(devices, True)

    def service_handle(service: ServiceCall) -> None:
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        source = service.data.get(ATTR_SOURCE)
        if entity_ids:
            devices = [
                device
                for device in hass.data[DATA_BLACKBIRD].values()
                if device.entity_id in entity_ids
            ]

        else:
            devices = hass.data[DATA_BLACKBIRD].values()

        for device in devices:
            if service.service == SERVICE_SETALLZONES:
                device.set_all_zones(source)

    hass.services.register(
        DOMAIN, SERVICE_SETALLZONES, service_handle, schema=BLACKBIRD_SETALLZONES_SCHEMA
    )


class BlackbirdZone(MediaPlayerEntity):
    """Representation of a Blackbird matrix zone."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, blackbird, sources, zone_id, zone_name):
        """Initialize new zone."""
        self._blackbird = blackbird
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._attr_source_list = sorted(
            self._source_name_id.keys(), key=lambda v: self._source_name_id[v]
        )
        self._zone_id = zone_id
        self._attr_name = zone_name

    def update(self):
        """Retrieve latest state."""
        state = self._blackbird.zone_status(self._zone_id)
        if not state:
            return
        self._attr_state = STATE_ON if state.power else STATE_OFF
        idx = state.av
        if idx in self._source_id_name:
            self._attr_source = self._source_id_name[idx]
        else:
            self._attr_source = None

    @property
    def media_title(self):
        """Return the current source as media title."""
        return self.source

    def set_all_zones(self, source):
        """Set all zones to one source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        _LOGGER.debug("Setting all zones source to %s", idx)
        self._blackbird.set_all_zone_source(idx)

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        _LOGGER.debug("Setting zone %d source to %s", self._zone_id, idx)
        self._blackbird.set_zone_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        _LOGGER.debug("Turning zone %d on", self._zone_id)
        self._blackbird.set_zone_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        _LOGGER.debug("Turning zone %d off", self._zone_id)
        self._blackbird.set_zone_power(self._zone_id, False)
