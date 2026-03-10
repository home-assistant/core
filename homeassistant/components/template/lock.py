"""Support for locks which integrates with other components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    LockEntity,
    LockEntityFeature,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import validators as template_validators
from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

CONF_CODE_FORMAT_TEMPLATE = "code_format_template"
CONF_CODE_FORMAT = "code_format"
CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"
CONF_OPEN = "open"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

LEGACY_FIELDS = {
    CONF_CODE_FORMAT_TEMPLATE: CONF_CODE_FORMAT,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

LOCK_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE_FORMAT): cv.template,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_OPEN): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_STATE): cv.template,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
    }
)

LOCK_YAML_SCHEMA = LOCK_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA).extend(
    make_template_entity_common_modern_schema(LOCK_DOMAIN, DEFAULT_NAME).schema
)

PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CODE_FORMAT_TEMPLATE): cv.template,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_OPEN): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)

LOCK_CONFIG_ENTRY_SCHEMA = LOCK_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template fans."""
    await async_setup_template_platform(
        hass,
        LOCK_DOMAIN,
        config,
        StateLockEntity,
        TriggerLockEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateLockEntity,
        LOCK_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_lock(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateLockEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateLockEntity,
        LOCK_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateLock(AbstractTemplateEntity, LockEntity):
    """Representation of a template lock features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._code_format_template_error: TemplateError | None = None

        self.setup_state_template(
            CONF_STATE,
            "_lock_state",
            template_validators.strenum(
                self, CONF_STATE, LockState, LockState.LOCKED, LockState.UNLOCKED
            ),
            self._set_state,
        )

        self.setup_template(
            CONF_CODE_FORMAT,
            "_attr_code_format",
            None,
            self._update_code_format,
            none_on_template_error=False,
        )

        for action_id, supported_feature in (
            (CONF_LOCK, 0),
            (CONF_UNLOCK, 0),
            (CONF_OPEN, LockEntityFeature.OPEN),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    def _set_state(self, state: LockState | None) -> None:
        if state is None:
            self._attr_is_locked = None
            return

        self._attr_is_jammed = state == LockState.JAMMED
        self._attr_is_opening = state == LockState.OPENING
        self._attr_is_locking = state == LockState.LOCKING
        self._attr_is_open = state == LockState.OPEN
        self._attr_is_unlocking = state == LockState.UNLOCKING
        self._attr_is_locked = state == LockState.LOCKED

    @callback
    def _update_code_format(self, render: str | TemplateError | None):
        """Update code format from the template."""
        if isinstance(render, TemplateError):
            self._attr_code_format = None
            self._code_format_template_error = render
        elif render in (None, "None", ""):
            self._attr_code_format = None
            self._code_format_template_error = None
        else:
            self._attr_code_format = render
            self._code_format_template_error = None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        # Check if we need to raise for incorrect code format
        # template before processing the action.
        self._raise_template_error_if_available()

        if self._attr_assumed_state:
            self._set_state(LockState.LOCKED)
            self.async_write_ha_state()

        tpl_vars = {ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None}

        await self.async_run_script(
            self._action_scripts[CONF_LOCK],
            run_variables=tpl_vars,
            context=self._context,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        # Check if we need to raise for incorrect code format
        # template before processing the action.
        self._raise_template_error_if_available()

        if self._attr_assumed_state:
            self._set_state(LockState.UNLOCKED)
            self.async_write_ha_state()

        tpl_vars = {ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None}

        await self.async_run_script(
            self._action_scripts[CONF_UNLOCK],
            run_variables=tpl_vars,
            context=self._context,
        )

    async def async_open(self, **kwargs: Any) -> None:
        """Open the device."""
        # Check if we need to raise for incorrect code format
        # template before processing the action.
        self._raise_template_error_if_available()

        if self._attr_assumed_state:
            self._set_state(LockState.OPEN)
            self.async_write_ha_state()

        tpl_vars = {ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None}

        await self.async_run_script(
            self._action_scripts[CONF_OPEN],
            run_variables=tpl_vars,
            context=self._context,
        )

    def _raise_template_error_if_available(self):
        """Raise an error if the rendered code format is not valid."""
        if self._code_format_template_error is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="code_format_template_error",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "code_format_template": self._templates[CONF_CODE_FORMAT].template,
                    "cause": str(self._code_format_template_error),
                },
            )


class StateLockEntity(TemplateEntity, AbstractTemplateLock):
    """Representation of a template lock."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the lock."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateLock.__init__(self, name, config)


class TriggerLockEntity(TriggerEntity, AbstractTemplateLock):
    """Lock entity based on trigger data."""

    domain = LOCK_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateLock.__init__(self, name, config)
