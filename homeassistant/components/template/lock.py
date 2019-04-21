"""
Support for locks which integrates with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.template/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.core import callback
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START, STATE_ON, STATE_LOCKED, MATCH_ALL)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

CONF_LOCK = 'lock'
CONF_UNLOCK = 'unlock'

DEFAULT_NAME = 'Template Lock'
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
    vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Template lock."""
    name = config.get(CONF_NAME)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    value_template_entity_ids = value_template.extract_entities()

    if value_template_entity_ids == MATCH_ALL:
        _LOGGER.warning(
            'Template lock %s has no entity ids configured to track nor '
            'were we able to extract the entities to track from the %s '
            'template. This entity will only be able to be updated '
            'manually.', name, CONF_VALUE_TEMPLATE)

    async_add_devices([TemplateLock(
        hass,
        name,
        value_template,
        value_template_entity_ids,
        config.get(CONF_LOCK),
        config.get(CONF_UNLOCK),
        config.get(CONF_OPTIMISTIC)
    )])


class TemplateLock(LockDevice):
    """Representation of a template lock."""

    def __init__(self, hass, name, value_template, entity_ids,
                 command_lock, command_unlock, optimistic):
        """Initialize the lock."""
        self._state = None
        self._hass = hass
        self._name = name
        self._state_template = value_template
        self._state_entities = entity_ids
        self._command_lock = Script(hass, command_lock)
        self._command_unlock = Script(hass, command_unlock)
        self._optimistic = optimistic

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_lock_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_lock_startup(event):
            """Update template on startup."""
            if self._state_entities != MATCH_ALL:
                # Track state change only for valid templates
                async_track_state_change(
                    self._hass, self._state_entities,
                    template_lock_state_listener)
            self.async_schedule_update_ha_state(True)

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_lock_startup)

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state

    async def async_update(self):
        """Update the state from the template."""
        try:
            self._state = self._state_template.async_render().lower() in (
                'true', STATE_ON, STATE_LOCKED)
        except TemplateError as ex:
            self._state = None
            _LOGGER.error('Could not render template %s: %s', self._name, ex)

    async def async_lock(self, **kwargs):
        """Lock the device."""
        if self._optimistic:
            self._state = True
            self.async_schedule_update_ha_state()
        await self._command_lock.async_run(context=self._context)

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        if self._optimistic:
            self._state = False
            self.async_schedule_update_ha_state()
        await self._command_unlock.async_run(context=self._context)
