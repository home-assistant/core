"""
Support for multiple covers which integrate with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.multicover/
"""
import asyncio
import logging
import re

import voluptuous as vol

from homeassistant.core import (callback, split_entity_id)
from homeassistant.components.cover import (
    ENTITY_ID_FORMAT, DOMAIN, PLATFORM_SCHEMA, CoverDevice,
    ATTR_POSITION, ATTR_TILT_POSITION, ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    SUPPORT_SET_POSITION, SUPPORT_OPEN_TILT, SUPPORT_CLOSE_TILT,
    SUPPORT_STOP_TILT, SUPPORT_SET_TILT_POSITION)
from homeassistant.components.zwave.const import EVENT_NETWORK_READY
from homeassistant.const import (
    CONF_COVERS, CONF_ENTITY_ID, CONF_FRIENDLY_NAME,
    EVENT_HOMEASSISTANT_START, EVENT_CALL_SERVICE,
    STATE_CLOSED, STATE_UNKNOWN, ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER, SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER, SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION, SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER, SERVICE_STOP_COVER_TILT,
    ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | \
                 SUPPORT_STOP | SUPPORT_SET_POSITION
TILT_FEATURES = SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | \
                SUPPORT_STOP_TILT | SUPPORT_SET_TILT_POSITION


CONF_ENTITY_ID_REGEX = 'entity_id_regex'
CONF_TILT = 'tilt'
CONF_WINTER_PROTECTION = 'winter_protection'
CONF_CLOSE_POSITION = 'close_position'
CONF_OPEN_POSITION = 'open_position'
CONF_TEMPERATURE_SENSOR = 'temperature_sensor'

KEY_OPEN_CLOSE = 'open_close'
KEY_STOP = 'stop'
KEY_POSITION = 'position'


WINTER_PROTECTION_SCHEMA = vol.All(vol.Schema({
    CONF_CLOSE_POSITION:
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    CONF_OPEN_POSITION:
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(int),
    vol.Required(CONF_TEMPERATURE_SENSOR): cv.entity_id,
}), cv.has_at_least_one_key(CONF_CLOSE_POSITION, CONF_OPEN_POSITION))

COVER_SCHEMA = vol.All(vol.Schema({
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    CONF_ENTITY_ID: cv.entity_ids,
    CONF_ENTITY_ID_REGEX: cv.string,
    vol.Optional(CONF_TILT): cv.boolean,
    vol.Optional(CONF_WINTER_PROTECTION): WINTER_PROTECTION_SCHEMA,
}), cv.has_at_least_one_key(CONF_ENTITY_ID, CONF_ENTITY_ID_REGEX))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MultiCover."""
    covers = []

    for device, device_config in config[CONF_COVERS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        entity_ids = device_config.get(CONF_ENTITY_ID, [])
        entity_ids_regex = device_config.get(CONF_ENTITY_ID_REGEX)
        tilt = device_config.get(CONF_TILT, False)

        winter_config = device_config.get(CONF_WINTER_PROTECTION, {})
        close_position = winter_config.get(CONF_CLOSE_POSITION)
        open_position = winter_config.get(CONF_OPEN_POSITION)
        temp = winter_config.get(ATTR_TEMPERATURE, 3)
        temp_sensor = winter_config.get(CONF_TEMPERATURE_SENSOR)
        covers.append(
            MultiCover(
                hass, device, friendly_name, entity_ids, entity_ids_regex,
                tilt, close_position, open_position, temp, temp_sensor)
        )

    if not covers:
        _LOGGER.error("No multicovers added")
        return False

    async_add_devices(covers, True)
    return True


class MultiCover(CoverDevice):
    """Representation of a MultiCover."""

    def __init__(self, hass, device_id, friendly_name,
                 entity_ids, entity_ids_regex, tilt,
                 close_position, open_position, temp, temp_sensor):
        """Initialize a multicover entity."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._device_id = device_id
        self._name = friendly_name
        self._entities = set(entity_ids)
        self._entity_ids_regex = entity_ids_regex
        self._tilt = tilt
        self._close_position = close_position
        self._open_position = open_position
        self._temp = temp
        self._temp_sensor = temp_sensor
        self.matched_entities = set()
        self.covers = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                       KEY_POSITION: set()}
        self.tilts = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                      KEY_POSITION: set()}
        self.winter_protection = False
        _LOGGER.debug("%s: {tilt: %s, temp: %s, temp_sensor: %s, "
                      "close_position: %s, open_position: %s}",
                      self._device_id, tilt, temp, temp_sensor,
                      close_position, open_position)

    def match_entities(self):
        """Return all matched entities based on regex if not matched before."""
        if self._entity_ids_regex is None:
            return False

        pattern = re.compile(self._entity_ids_regex, re.I | re.M)
        all_entities = ', '.join(self.hass.states.async_entity_ids(DOMAIN))
        match_all = set(re.findall(pattern, all_entities))

        for match in match_all:
            if match not in self.matched_entities:
                self._entities.add(match)

        self.matched_entities = self.matched_entities.union(match_all)

    def check_supported_features(self):
        """Iterate through entity list and check supported features."""
        all_entities = set()
        for entity in self._entities.copy():
            if entity == self.entity_id:
                _LOGGER.warning("%s: The entity_id of this component \"%s\" "
                                "is not allowed.", self._device_id, entity)
                self._entities.remove(entity)
                continue
            if split_entity_id(entity)[0] != DOMAIN:
                _LOGGER.warning("%s: Only cover entities are allowed. Please "
                                "remove: \"%s\".", self._device_id, entity)
                self._entities.remove(entity)
                continue
            state = self.hass.states.get(entity)
            if state is None:
                continue
            all_entities.add(entity)
            self._entities.remove(entity)
            features = state.attributes[ATTR_SUPPORTED_FEATURES]
            # Supported features for covers
            if features & 1 and features & 2:
                self.covers[KEY_OPEN_CLOSE].add(entity)
            if features & 4:
                self.covers[KEY_POSITION].add(entity)
            if features & 8:
                self.covers[KEY_STOP].add(entity)
            # Supported features for tilts
            if features & 16 and features & 32:
                self.tilts[KEY_OPEN_CLOSE].add(entity)
            if features & 64:
                self.tilts[KEY_STOP].add(entity)
            if features & 128:
                self.tilts[KEY_POSITION].add(entity)
        if len(self._entities) > 0:
            _LOGGER.debug("%s: Entities not found: %s",
                          self._device_id, self._entities)
        return all_entities

    def temp_state_change(self, state):
        """Update winter_protection based on state change."""
        self.winter_protection = bool(
            state is not None and state.state != STATE_UNKNOWN and
            float(state.state) < self._temp)
        _LOGGER.debug("%s: Winter protection enabled: %s",
                      self._device_id, self.winter_protection)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def multicover_state_listener(entity, old_state, new_state):
            """Handle cover state changes and update state."""
            self.async_schedule_update_ha_state(True)

        @callback
        def multicover_temp_state_listener(entity, old_state, new_state):
            """Handle temperature sensore changes."""
            self.temp_state_change(new_state)

        @callback
        def multicover_startup(event):
            """Update MultiCover after startup."""
            # Check entity features and add state change listeners.
            self.match_entities()
            entities = self.check_supported_features()
            async_track_state_change(
                self.hass, entities, multicover_state_listener)
            # Check if winter protection feature is used.
            if self._temp_sensor:
                async_track_state_change(self.hass, self._temp_sensor,
                                         multicover_temp_state_listener)
                self.temp_state_change(self.hass.states.get(self._temp_sensor))

            self.async_schedule_update_ha_state(True)
            _LOGGER.debug("%s: Finished taskes after HomeAssistant startup.",
                          self._device_id)

        @callback
        def multicover_zwave_startup(event):
            """Update MultiCover after ZWave Network startup."""
            self.match_entities()
            entities = self.check_supported_features()
            async_track_state_change(
                self.hass, entities, multicover_state_listener)
            self.async_schedule_update_ha_state(True)
            _LOGGER.debug("%s: Finished taskes after ZWave Network war ready.",
                          self._device_id)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, multicover_startup)
        self.hass.bus.async_listen_once(
            EVENT_NETWORK_READY, multicover_zwave_startup)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def assumed_state(self):
        """Enable buttons even if at end position."""
        return True

    @property
    def should_poll(self):
        """Disable polling for the MultiCover."""
        return False

    @property
    def is_closed(self):
        """Return if all covers in group are closed."""
        if len(self.covers[KEY_OPEN_CLOSE]) == 0:
            return False
        for entity_id in self.covers[KEY_OPEN_CLOSE]:
            state = self.hass.states.get(entity_id)
            if state is None or state.state != STATE_CLOSED:
                return False
        return True

    @property
    def current_cover_position(self):
        """Return current position for all covers.

        None is unknown. pos if all have the same position.
        Else 0 if closed or 100 is fully open.
        """
        position = -1
        for entity_id in self.covers[KEY_POSITION]:
            state = self.hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position
        else:
            return 0 if self.is_closed else 100

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position for all covers.

        None is unknown. pos if all have the same tilt position.
        Else 100 for tilt open.
        """
        if self._tilt is False:
            return None

        position = -1
        for entity_id in self.tilts[KEY_POSITION]:
            state = self.hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position
        else:
            return 100

    @property
    def state_attributes(self):
        """Return the current position as attribute."""
        data = {}
        current_cover = self.current_cover_position
        current_tilt = self.current_cover_tilt_position
        if current_cover is not None:
            data[ATTR_CURRENT_POSITION] = current_cover
        if current_tilt is not None:
            data[ATTR_CURRENT_TILT_POSITION] = current_tilt
        return data

    @property
    def supported_features(self):
        """Flag supported features for a cover.

        Currently doesn't support tilt features.
        """
        supported_features = COVER_FEATURES

        if self._tilt:
            supported_features |= TILT_FEATURES

        return supported_features

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Move the covers up."""
        _LOGGER.debug("Open covers called")
        if self.winter_protection and self._open_position:
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_OPEN_COVER,
                    'service_data': {'entity_id': self.covers[KEY_OPEN_CLOSE] -
                                                  self.covers[KEY_POSITION]}})
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_SET_COVER_POSITION,
                    'service_data': {'entity_id': self.covers[KEY_POSITION],
                                     ATTR_POSITION: self._open_position}})
        else:
            covers = self.covers['open_close'].union(self.covers[KEY_POSITION])
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_OPEN_COVER,
                    'service_data': {'entity_id': covers}})

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Move the covers down."""
        _LOGGER.debug("Close covers called")
        if self.winter_protection and self._close_position:
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_CLOSE_COVER,
                    'service_data': {'entity_id': self.covers[KEY_OPEN_CLOSE] -
                                                  self.covers[KEY_POSITION]}})
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_SET_COVER_POSITION,
                    'service_data': {'entity_id': self.covers[KEY_POSITION],
                                     ATTR_POSITION: self._close_position}})
        else:
            covers = \
                self.covers[KEY_OPEN_CLOSE].union(self.covers[KEY_POSITION])
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, {
                    'domain': DOMAIN, 'service': SERVICE_CLOSE_COVER,
                    'service_data': {'entity_id': covers}})

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        _LOGGER.debug("Stop covers called")
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_STOP_COVER,
                'service_data': {'entity_id': self.covers[KEY_STOP]}})

    @asyncio.coroutine
    def async_set_cover_position(self, **kwargs):
        """Set covers position."""
        position = kwargs[ATTR_POSITION]
        _LOGGER.debug("Set cover position called: %d", position)
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_SET_COVER_POSITION,
                'service_data': {'entity_id': self.covers[KEY_POSITION],
                                 ATTR_POSITION: position}})

    @asyncio.coroutine
    def async_open_cover_tilt(self, **kwargs):
        """Tilt covers open."""
        _LOGGER.debug("Open tilts called")
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_OPEN_COVER_TILT,
                'service_data': {'entity_id': self.tilts[KEY_OPEN_CLOSE]}})

    @asyncio.coroutine
    def async_close_cover_tilt(self, **kwargs):
        """Tilt covers closed."""
        _LOGGER.debug("Close tilts called")
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_CLOSE_COVER_TILT,
                'service_data': {'entity_id': self.tilts[KEY_OPEN_CLOSE]}})

    @asyncio.coroutine
    def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        _LOGGER.debug("Stop tilts called")
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_STOP_COVER_TILT,
                'service_data': {'entity_id': self.tilts[KEY_STOP]}})

    @asyncio.coroutine
    def async_set_cover_tilt_position(self, **kwargs):
        """Set tilt position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        _LOGGER.debug("Set tilt position called: %d", tilt_position)
        self.hass.bus.async_fire(
            EVENT_CALL_SERVICE, {
                'domain': DOMAIN, 'service': SERVICE_SET_COVER_TILT_POSITION,
                'service_data': {'entity_id': self.tilts[KEY_POSITION],
                                 ATTR_TILT_POSITION: tilt_position}})
