"""Support for locks which integrates with other components."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.lock import (
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    LockEntity,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers import selector, template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

CONF_CODE_FORMAT = "code_format"
CONF_CODE_FORMAT_TEMPLATE = "code_format_template"
CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_CODE_FORMAT_TEMPLATE: CONF_CODE_FORMAT,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

LOCK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_CODE_FORMAT): cv.template,
        vol.Optional(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    }
).extend(TEMPLATE_ENTITY_COMMON_SCHEMA.schema)

LOCK_CONFIG_SCHEMA = LOCK_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)

LEGACY_LOCK_SCHEMA = vol.Schema(
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


def rewrite_legacy_to_modern_conf(hass: HomeAssistant, cfg: dict[str, dict]) -> dict:
    """Rewrite legacy lock definitions to modern ones."""
    entity_cfg = rewrite_common_legacy_to_modern_conf(hass, cfg, LEGACY_FIELDS)

    unique_id = entity_cfg.get(CONF_UNIQUE_ID)

    if CONF_NAME not in entity_cfg and unique_id is not None:
        entity_cfg[CONF_NAME] = template.Template(unique_id, hass)

    return entity_cfg


PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(LEGACY_LOCK_SCHEMA.schema)


async def _async_create_entities(hass, config, unique_id_prefix=None):
    """Create the Template lock."""
    locks = []

    for entity_config in config:
        unique_id = entity_config.get(CONF_UNIQUE_ID)
        if unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        locks.append(TemplateLock(hass, entity_config, unique_id))

    return locks


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lock."""
    if discovery_info is None:
        async_add_entities(
            await _async_create_entities(
                hass,
                [rewrite_legacy_to_modern_conf(hass, config)],
            )
        )
        return

    async_add_entities(
        await _async_create_entities(
            hass,
            discovery_info["entities"],
            discovery_info["unique_id"],
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = LOCK_CONFIG_SCHEMA(_options)
    async_add_entities(
        [
            TemplateLock(
                hass,
                validated_config,
                config_entry.entry_id,
            )
        ]
    )


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
        self._state_template = config.get(CONF_STATE)
        self._command_lock = Script(hass, config[CONF_LOCK], name, DOMAIN)
        self._command_unlock = Script(hass, config[CONF_UNLOCK], name, DOMAIN)
        self._code_format_template = config.get(CONF_CODE_FORMAT)
        self._code_format = None
        self._code_format_template_error = None
        self._optimistic = config.get(CONF_OPTIMISTIC)
        self._attr_assumed_state = bool(self._optimistic)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state in ("true", STATE_ON, LockState.LOCKED)

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._state == LockState.JAMMED

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == LockState.UNLOCKING

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._state == LockState.LOCKING

    @callback
    def _update_state(self, result):
        """Update the state from the template."""
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        if isinstance(result, bool):
            self._state = LockState.LOCKED if result else LockState.UNLOCKED
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
