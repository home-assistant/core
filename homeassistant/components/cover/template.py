"""
Support for covers which integrate with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.cover import (
    ENTITY_ID_FORMAT, CoverDevice, PLATFORM_SCHEMA,
    SUPPORT_OPEN_TILT, SUPPORT_CLOSE_TILT, SUPPORT_STOP_TILT,
    SUPPORT_SET_TILT_POSITION, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    SUPPORT_SET_POSITION, ATTR_POSITION, ATTR_TILT_POSITION)
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_ENTITY_ID,
    EVENT_HOMEASSISTANT_START, MATCH_ALL,
    CONF_VALUE_TEMPLATE, CONF_ICON_TEMPLATE,
    CONF_ENTITY_PICTURE_TEMPLATE, CONF_OPTIMISTIC,
    STATE_OPEN, STATE_CLOSED)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_OPEN, STATE_CLOSED, 'true', 'false']

CONF_COVERS = 'covers'

CONF_POSITION_TEMPLATE = 'position_template'
CONF_TILT_TEMPLATE = 'tilt_template'
OPEN_ACTION = 'open_cover'
CLOSE_ACTION = 'close_cover'
STOP_ACTION = 'stop_cover'
POSITION_ACTION = 'set_cover_position'
TILT_ACTION = 'set_cover_tilt_position'
CONF_TILT_OPTIMISTIC = 'tilt_optimistic'

CONF_VALUE_OR_POSITION_TEMPLATE = 'value_or_position'
CONF_OPEN_OR_CLOSE = 'open_or_close'

TILT_FEATURES = (SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_STOP_TILT |
                 SUPPORT_SET_TILT_POSITION)

COVER_SCHEMA = vol.Schema({
    vol.Inclusive(OPEN_ACTION, CONF_OPEN_OR_CLOSE): cv.SCRIPT_SCHEMA,
    vol.Inclusive(CLOSE_ACTION, CONF_OPEN_OR_CLOSE): cv.SCRIPT_SCHEMA,
    vol.Optional(STOP_ACTION): cv.SCRIPT_SCHEMA,
    vol.Exclusive(CONF_POSITION_TEMPLATE,
                  CONF_VALUE_OR_POSITION_TEMPLATE): cv.template,
    vol.Exclusive(CONF_VALUE_TEMPLATE,
                  CONF_VALUE_OR_POSITION_TEMPLATE): cv.template,
    vol.Optional(CONF_POSITION_TEMPLATE): cv.template,
    vol.Optional(CONF_TILT_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
    vol.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Template cover."""
    covers = []

    for device, device_config in config[CONF_COVERS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        position_template = device_config.get(CONF_POSITION_TEMPLATE)
        tilt_template = device_config.get(CONF_TILT_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        open_action = device_config.get(OPEN_ACTION)
        close_action = device_config.get(CLOSE_ACTION)
        stop_action = device_config.get(STOP_ACTION)
        position_action = device_config.get(POSITION_ACTION)
        tilt_action = device_config.get(TILT_ACTION)
        optimistic = device_config.get(CONF_OPTIMISTIC)
        tilt_optimistic = device_config.get(CONF_TILT_OPTIMISTIC)

        if position_action is None and open_action is None:
            _LOGGER.error('Must specify at least one of %s' or '%s',
                          OPEN_ACTION, POSITION_ACTION)
            continue
        template_entity_ids = set()
        if state_template is not None:
            temp_ids = state_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if position_template is not None:
            temp_ids = position_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if tilt_template is not None:
            temp_ids = tilt_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if icon_template is not None:
            temp_ids = icon_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if entity_picture_template is not None:
            temp_ids = entity_picture_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if not template_entity_ids:
            template_entity_ids = MATCH_ALL

        entity_ids = device_config.get(CONF_ENTITY_ID, template_entity_ids)

        covers.append(
            CoverTemplate(
                hass,
                device, friendly_name, state_template,
                position_template, tilt_template, icon_template,
                entity_picture_template, open_action, close_action,
                stop_action, position_action, tilt_action,
                optimistic, tilt_optimistic, entity_ids
            )
        )
    if not covers:
        _LOGGER.error("No covers added")
        return False

    async_add_devices(covers)
    return True


class CoverTemplate(CoverDevice):
    """Representation of a Template cover."""

    def __init__(self, hass, device_id, friendly_name, state_template,
                 position_template, tilt_template, icon_template,
                 entity_picture_template, open_action, close_action,
                 stop_action, position_action, tilt_action,
                 optimistic, tilt_optimistic, entity_ids):
        """Initialize the Template cover."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._position_template = position_template
        self._tilt_template = tilt_template
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._open_script = None
        if open_action is not None:
            self._open_script = Script(hass, open_action)
        self._close_script = None
        if close_action is not None:
            self._close_script = Script(hass, close_action)
        self._stop_script = None
        if stop_action is not None:
            self._stop_script = Script(hass, stop_action)
        self._position_script = None
        if position_action is not None:
            self._position_script = Script(hass, position_action)
        self._tilt_script = None
        if tilt_action is not None:
            self._tilt_script = Script(hass, tilt_action)
        self._optimistic = (optimistic or
                            (not state_template and not position_template))
        self._tilt_optimistic = tilt_optimistic or not tilt_template
        self._icon = None
        self._entity_picture = None
        self._position = None
        self._tilt_value = None
        self._entities = entity_ids

        if self._template is not None:
            self._template.hass = self.hass
        if self._position_template is not None:
            self._position_template.hass = self.hass
        if self._tilt_template is not None:
            self._tilt_template.hass = self.hass
        if self._icon_template is not None:
            self._icon_template.hass = self.hass
        if self._entity_picture_template is not None:
            self._entity_picture_template.hass = self.hass

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_cover_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_cover_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, template_cover_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_cover_startup)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._position == 0

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._tilt_value

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

        if self._stop_script is not None:
            supported_features |= SUPPORT_STOP

        if self._position_script is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= TILT_FEATURES

        return supported_features

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Move the cover up."""
        if self._open_script:
            yield from self._open_script.async_run()
        elif self._position_script:
            yield from self._position_script.async_run({"position": 100})
        if self._optimistic:
            self._position = 100
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Move the cover down."""
        if self._close_script:
            yield from self._close_script.async_run()
        elif self._position_script:
            yield from self._position_script.async_run({"position": 0})
        if self._optimistic:
            self._position = 0
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        if self._stop_script:
            yield from self._stop_script.async_run()

    @asyncio.coroutine
    def async_set_cover_position(self, **kwargs):
        """Set cover position."""
        self._position = kwargs[ATTR_POSITION]
        yield from self._position_script.async_run(
            {"position": self._position})
        if self._optimistic:
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_open_cover_tilt(self, **kwargs):
        """Tilt the cover open."""
        self._tilt_value = 100
        yield from self._tilt_script.async_run({"tilt": self._tilt_value})
        if self._tilt_optimistic:
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_close_cover_tilt(self, **kwargs):
        """Tilt the cover closed."""
        self._tilt_value = 0
        yield from self._tilt_script.async_run(
            {"tilt": self._tilt_value})
        if self._tilt_optimistic:
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self._tilt_value = kwargs[ATTR_TILT_POSITION]
        yield from self._tilt_script.async_run({"tilt": self._tilt_value})
        if self._tilt_optimistic:
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_update(self):
        """Update the state from the template."""
        if self._template is not None:
            try:
                state = self._template.async_render().lower()
                if state in _VALID_STATES:
                    if state in ('true', STATE_OPEN):
                        self._position = 100
                    else:
                        self._position = 0
                else:
                    _LOGGER.error(
                        'Received invalid cover is_on state: %s. Expected: %s',
                        state, ', '.join(_VALID_STATES))
                    self._position = None
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._position = None
        if self._position_template is not None:
            try:
                state = float(self._position_template.async_render())
                if state < 0 or state > 100:
                    self._position = None
                    _LOGGER.error("Cover position value must be"
                                  " between 0 and 100."
                                  " Value was: %.2f", state)
                else:
                    self._position = state
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._position = None
            except ValueError as ex:
                _LOGGER.error(ex)
                self._position = None
        if self._tilt_template is not None:
            try:
                state = float(self._tilt_template.async_render())
                if state < 0 or state > 100:
                    self._tilt_value = None
                    _LOGGER.error("Tilt value must be between 0 and 100."
                                  " Value was: %.2f", state)
                else:
                    self._tilt_value = state
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._tilt_value = None
            except ValueError as ex:
                _LOGGER.error(ex)
                self._tilt_value = None

        for property_name, template in (
                ('_icon', self._icon_template),
                ('_entity_picture', self._entity_picture_template)):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._name)
                    return

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._name, ex)
