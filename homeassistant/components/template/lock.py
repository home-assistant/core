"""Support for locks which integrates with other components."""
import voluptuous as vol

from homeassistant.components.lock import (
    PLATFORM_SCHEMA,
    STATE_JAMMED,
    STATE_LOCKING,
    STATE_UNLOCKING,
    LockEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_LOCKED,
    STATE_ON,
    STATE_UNLOCKED,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE, DOMAIN
from .template_entity import TemplateEntity

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
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def _async_create_entities(hass, config):
    """Create the Template lock."""
    device = config.get(CONF_NAME)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    availability_template = config.get(CONF_AVAILABILITY_TEMPLATE)

    return [
        TemplateLock(
            hass,
            device,
            value_template,
            availability_template,
            config.get(CONF_LOCK),
            config.get(CONF_UNLOCK),
            config.get(CONF_OPTIMISTIC),
            config.get(CONF_UNIQUE_ID),
        )
    ]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template lock."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateLock(TemplateEntity, LockEntity):
    """Representation of a template lock."""

    def __init__(
        self,
        hass,
        name,
        value_template,
        availability_template,
        command_lock,
        command_unlock,
        optimistic,
        unique_id,
    ):
        """Initialize the lock."""
        super().__init__(availability_template=availability_template)
        self._state = None
        self._name = name
        self._state_template = value_template
        self._command_lock = Script(hass, command_lock, name, DOMAIN)
        self._command_unlock = Script(hass, command_unlock, name, DOMAIN)
        self._optimistic = optimistic
        self._unique_id = unique_id

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this lock."""
        return self._unique_id

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state in ("true", STATE_ON, STATE_LOCKED)

    @property
    def is_jammed(self):
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_unlocking(self):
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_locking(self):
        """Return true if lock is locking."""
        return self._state == STATE_LOCKING

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        if isinstance(result, bool):
            self._state = STATE_LOCKED if result else STATE_UNLOCKED
            return

        if isinstance(result, str):
            self._state = result.lower()
            return

        self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute(
            "_state", self._state_template, None, self._update_state
        )
        await super().async_added_to_hass()

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
