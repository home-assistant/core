"""Support for locks which integrates with other components."""

from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
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
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PICTURE, DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .template_entity import (
    LEGACY_FIELDS as TEMPLATE_ENTITY_LEGACY_FIELDS,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TemplateEntity,
    make_template_entity_common_modern_schema,
    rewrite_common_legacy_to_modern_conf,
)
from .trigger_entity import TriggerEntity

CONF_CODE_FORMAT_TEMPLATE = "code_format_template"
CONF_CODE_FORMAT = "code_format"
CONF_LOCK = "lock"
CONF_UNLOCK = "unlock"
CONF_OPEN = "open"

DEFAULT_NAME = "Template Lock"
DEFAULT_OPTIMISTIC = False

LEGACY_FIELDS = TEMPLATE_ENTITY_LEGACY_FIELDS | {
    CONF_CODE_FORMAT_TEMPLATE: CONF_CODE_FORMAT,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

LOCK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_CODE_FORMAT): cv.template,
            vol.Required(CONF_LOCK): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_OPEN): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Required(CONF_STATE): cv.template,
            vol.Required(CONF_UNLOCK): cv.SCRIPT_SCHEMA,
        }
    ).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)
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

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerLockEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class AbstractTemplateLock(AbstractTemplateEntity, LockEntity):
    """Representation of a template lock features."""

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._state: LockState | None = None
        self._state_template = config.get(CONF_STATE)
        self._code_format_template = config.get(CONF_CODE_FORMAT)
        self._code_format: str | None = None
        self._code_format_template_error: TemplateError | None = None
        self._optimistic = config.get(CONF_OPTIMISTIC)
        self._attr_assumed_state = bool(self._optimistic)

    def _iterate_scripts(
        self, config: dict[str, Any]
    ) -> Generator[tuple[str, Sequence[dict[str, Any]], LockEntityFeature | int]]:
        for action_id, supported_feature in (
            (CONF_LOCK, 0),
            (CONF_UNLOCK, 0),
            (CONF_OPEN, LockEntityFeature.OPEN),
        ):
            if (action_config := config.get(action_id)) is not None:
                yield (action_id, action_config, supported_feature)

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

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._code_format

    def _handle_state(self, result: Any) -> None:
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


class TemplateLock(TemplateEntity, AbstractTemplateLock):
    """Representation of a template lock."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the lock."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        AbstractTemplateLock.__init__(self, config)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

    @callback
    def _update_state(self, result: str | TemplateError) -> None:
        """Update the state from the template."""
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        self._handle_state(result)

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


class TriggerLockEntity(TriggerEntity, AbstractTemplateLock):
    """Lock entity based on trigger data."""

    domain = LOCK_DOMAIN
    extra_template_keys = (CONF_STATE,)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateLock.__init__(self, config)

        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        if isinstance(config.get(CONF_CODE_FORMAT), template.Template):
            self._to_render_simple.append(CONF_CODE_FORMAT)
            self._parse_result.add(CONF_CODE_FORMAT)

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, updater in (
            (CONF_STATE, self._handle_state),
            (CONF_CODE_FORMAT, self._update_code_format),
        ):
            if (rendered := self._rendered.get(key)) is not None:
                updater(rendered)
                write_ha_state = True

        if not self._optimistic:
            self.async_set_context(self.coordinator.data["context"])
            write_ha_state = True
        elif self._optimistic and len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
