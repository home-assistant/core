"""Support for locks which integrates with other components."""
from __future__ import annotations

from typing import Any

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)


async def _async_create_entities(hass, config):
    """Create the Template lock."""
    config = rewrite_common_legacy_to_modern_conf(config)
    return [TemplateLock(hass, config, config.get(CONF_UNIQUE_ID))]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lock."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateLock(TemplateEntity, LockEntity):
    """Representation of a template lock."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        config,
        unique_id,
    ):
        """Initialize the lock."""
        super().__init__(
            hass, config=config, fallback_name=DEFAULT_NAME, unique_id=unique_id
        )
        self._state = None
        name = self._attr_name
        self._state_template = config.get(CONF_VALUE_TEMPLATE)
        self._command_lock = Script(hass, config[CONF_LOCK], name, DOMAIN)
        self._command_unlock = Script(hass, config[CONF_UNLOCK], name, DOMAIN)
        self._optimistic = config.get(CONF_OPTIMISTIC)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return bool(self._optimistic)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state in ("true", STATE_ON, STATE_LOCKED)

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_locking(self) -> bool:
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

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.add_template_attribute(
            "_state", self._state_template, None, self._update_state
        )
        await super().async_added_to_hass()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()
        await self.async_run_script(self._command_lock, context=self._context)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        if self._optimistic:
            self._state = False
            self.async_write_ha_state()
        await self.async_run_script(self._command_unlock, context=self._context)
