"""Support for locks which integrates with other components."""
import logging

import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, LockDevice
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
    STATE_LOCKED,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

from . import extract_entities, initialise_templates
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)

CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Template lock."""
    device = config.get(CONF_NAME)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    availability_template = config.get(CONF_AVAILABILITY_TEMPLATE)

    templates = {
        CONF_VALUE_TEMPLATE: value_template,
        CONF_AVAILABILITY_TEMPLATE: availability_template,
    }

    initialise_templates(hass, templates)
    entity_ids = extract_entities(device, "lock", None, templates)

    async_add_devices(
        [
            TemplateLock(
                hass,
                device,
                value_template,
                availability_template,
                entity_ids,
                config.get(CONF_LOCK),
                config.get(CONF_UNLOCK),
                config.get(CONF_OPTIMISTIC),
            )
        ]
    )


class TemplateLock(LockDevice):
    """Representation of a template lock."""

    def __init__(
        self,
        hass,
        name,
        value_template,
        availability_template,
        entity_ids,
        command_lock,
        command_unlock,
        optimistic,
    ):
        """Initialize the lock."""
        self._state = None
        self._hass = hass
        self._name = name
        self._state_template = value_template
        self._availability_template = availability_template
        self._state_entities = entity_ids
        self._command_lock = Script(hass, command_lock)
        self._command_unlock = Script(hass, command_unlock)
        self._optimistic = optimistic
        self._available = True

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
                    self._hass, self._state_entities, template_lock_state_listener
                )
            self.async_schedule_update_ha_state(True)

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_lock_startup
        )

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

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    async def async_update(self):
        """Update the state from the template."""
        try:
            self._state = self._state_template.async_render().lower() in (
                "true",
                STATE_ON,
                STATE_LOCKED,
            )
        except TemplateError as ex:
            self._state = None
            _LOGGER.error("Could not render template %s: %s", self._name, ex)

        if self._availability_template is not None:
            try:
                self._available = (
                    self._availability_template.async_render().lower() == "true"
                )
            except (TemplateError, ValueError) as ex:
                _LOGGER.error(
                    "Could not render %s template %s: %s",
                    CONF_AVAILABILITY_TEMPLATE,
                    self._name,
                    ex,
                )

    async def async_lock(self, **kwargs):
        """Lock the device."""
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()
        await self._command_lock.async_run(context=self._context)

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        if self._optimistic:
            self._state = False
            self.async_write_ha_state()
        await self._command_unlock.async_run(context=self._context)
