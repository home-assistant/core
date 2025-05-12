"""Support for locks which integrates with other components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.lock import (
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    LockEntity,
    LockEntityFeature,
    LockState,
)
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

CONF_CODE_FORMAT_TEMPLATE = "code_format_template"
CONF_CODE_FORMAT = "code_format"
CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"
CONF_OPEN = "open"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_VALUE_TEMPLATE: CONF_STATE,
    CONF_CODE_FORMAT_TEMPLATE: CONF_CODE_FORMAT,
}

LOCK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_CODE_FORMAT): cv.template,
            vol.Optional(CONF_NAME): cv.template,
            vol.Optional(CONF_OPEN): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_STATE): cv.template,
            vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        }
    )
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema),
)


PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_OPEN): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_CODE_FORMAT_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template fans."""
    fans = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        fans.append(
            TemplateLock(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(fans)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template fans."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            [rewrite_common_legacy_to_modern_conf(hass, config, LEGACY_FIELDS)],
            None,
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class TemplateLock(TemplateEntity, LockEntity):
    """Representation of a template lock."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the lock."""
        super().__init__(
            hass, config=config, fallback_name=DEFAULT_NAME, unique_id=unique_id
        )
        self._state: LockState | None = None
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        self._state_template = config.get(CONF_STATE)
        for action_id, supported_feature in (
            (CONF_LOCK, 0),
            (CONF_UNLOCK, 0),
            (CONF_OPEN, LockEntityFeature.OPEN),
        ):
            # Scripts can be an empty list, therefore we need to check for None
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature
        self._code_format_template = config.get(CONF_CODE_FORMAT)
        self._code_format: str | None = None
        self._code_format_template_error: TemplateError | None = None
        self._optimistic = config.get(CONF_OPTIMISTIC)
        self._attr_assumed_state = bool(self._optimistic)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == LockState.LOCKED

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

    @property
    def is_open(self) -> bool:
        """Return true if lock is open."""
        return self._state == LockState.OPEN

    @callback
    def _update_state(self, result: str | TemplateError) -> None:
        """Update the state from the template."""
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        if isinstance(result, bool):
            self._state = LockState.LOCKED if result else LockState.UNLOCKED
            return

        if isinstance(result, str):
            if result.lower() in (
                "true",
                "on",
                "locked",
            ):
                self._state = LockState.LOCKED
            elif result.lower() in (
                "false",
                "off",
                "unlocked",
            ):
                self._state = LockState.UNLOCKED
            else:
                try:
                    self._state = LockState(result.lower())
                except ValueError:
                    self._state = None
            return

        self._state = None

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._code_format

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if TYPE_CHECKING:
            assert self._state_template is not None
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
        # Check if we need to raise for incorrect code format
        # template before processing the action.
        self._raise_template_error_if_available()

        if self._optimistic:
            self._state = LockState.LOCKED
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

        if self._optimistic:
            self._state = LockState.UNLOCKED
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

        if self._optimistic:
            self._state = LockState.OPEN
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
                    "code_format_template": self._code_format_template.template,
                    "cause": str(self._code_format_template_error),
                },
            )
