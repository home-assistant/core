"""Support for locks which integrates with other components."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.lock import (
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    STATE_JAMMED,
    STATE_LOCKING,
    STATE_UNLOCKING,
    LockEntity,
)
from homeassistant.const import (
    ATTR_CODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_LOCKED,
    STATE_ON,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
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

CONF_CODE_FORMAT_TEMPLATE = "code_format_template"
CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_CODE_FORMAT_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)


async def _async_create_entities(hass, config):
    """Create the Template lock."""
    config = rewrite_common_legacy_to_modern_conf(hass, config)
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
        self._code_format_template = config.get(CONF_CODE_FORMAT_TEMPLATE)
        self._code_format = None
        self._code_format_template_error = None
        self._optimistic = config.get(CONF_OPTIMISTIC)
        self._attr_assumed_state = bool(self._optimistic)

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
        """Update the state from the template."""
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

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._code_format

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute(
            "_state", self._state_template, None, self._update_state
        )
        if self._code_format_template:
            self.add_template_attribute(
                "_code_format_template",
                self._code_format_template,
                None,
                self._update_code_format,
            )
        super()._async_setup_templates()

    @callback
    def _update_code_format(self, render: str | TemplateError | None):
        """Update code format from the template."""
        if isinstance(render, TemplateError):
            self._code_format = None
            self._code_format_template_error = render
        elif render in (None, "None", ""):
            self._code_format = None
            self._code_format_template_error = None
        else:
            self._code_format = render
            self._code_format_template_error = None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._raise_template_error_if_available()

        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

        tpl_vars = {ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None}

        await self.async_run_script(
            self._command_lock, run_variables=tpl_vars, context=self._context
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._raise_template_error_if_available()

        if self._optimistic:
            self._state = False
            self.async_write_ha_state()

        tpl_vars = {ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None}

        await self.async_run_script(
            self._command_unlock, run_variables=tpl_vars, context=self._context
        )

    def _raise_template_error_if_available(self):
        if self._code_format_template_error is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="code_format_template_error",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "code_format_template": self._code_format_template.template,
                    "cause": str(self._code_format_template_error),
                },
            )
