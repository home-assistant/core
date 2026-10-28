"""Entities for the script integration."""

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import TYPE_CHECKING, Any, override

import probatio
from propcache.api import cached_property

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.components.trace import ATTR_ITEM_ID, ATTR_RUN_ID
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_NAME,
    CONF_ALIAS,
    CONF_DESCRIPTION,
    CONF_ICON,
    CONF_MODE,
    CONF_NAME,
    CONF_PATH,
    CONF_SEQUENCE,
    CONF_VARIABLES,
)
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import (
    ATTR_CUR,
    ATTR_MAX,
    CONF_MAX,
    CONF_MAX_EXCEEDED,
    Script,
    ScriptRunResult,
    script_stack_cv,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.trace import trace_get, trace_path
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import parse_datetime

from .config import ValidationStatus
from .const import (
    ATTR_LAST_ACTION,
    ATTR_LAST_TRIGGERED,
    CONF_FIELDS,
    CONF_TRACE,
    DOMAIN,
    ENTITY_ID_FORMAT,
    EVENT_SCRIPT_STARTED,
)
from .trace import trace_script

SCRIPT_SERVICE_SCHEMA = probatio.Schema(dict)


class BaseScriptEntity(ToggleEntity, ABC):
    """Base class for script entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {ATTR_LAST_TRIGGERED, ATTR_MODE, ATTR_CUR, ATTR_MAX, ATTR_LAST_ACTION}
    )

    raw_config: ConfigType | None

    @cached_property
    @abstractmethod
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""

    @cached_property
    @abstractmethod
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""

    @cached_property
    @abstractmethod
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @cached_property
    @abstractmethod
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""

    @cached_property
    @abstractmethod
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""


class UnavailableScriptEntity(BaseScriptEntity):
    """A non-functional script entity with its state set to unavailable.

    This class is instantiated when an script fails to validate.
    """

    _attr_should_poll = False
    _attr_available = False

    def __init__(
        self,
        key: str,
        raw_config: ConfigType | None,
        raw_blueprint_inputs: ConfigType | None,
        validation_error: str,
        validation_status: ValidationStatus,
    ) -> None:
        """Initialize a script entity."""
        self._attr_name = raw_config.get(CONF_ALIAS, key) if raw_config else key
        self._attr_unique_id = key
        self.raw_config = raw_config
        self._raw_blueprint_inputs = raw_blueprint_inputs
        self._validation_error = validation_error
        self._validation_status = validation_status

    @cached_property
    @override
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        return set()

    @cached_property
    @override
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""
        return set()

    @cached_property
    @override
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        return set()

    @property
    @override
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        # The config is invalid, but it can still point at its blueprint. Once
        # the blueprint was applied, only its inputs hold that reference.
        for config in (self._raw_blueprint_inputs, self.raw_config):
            if (
                config is not None
                and isinstance(blueprint := config.get(CONF_USE_BLUEPRINT), dict)
                and isinstance(path := blueprint.get(CONF_PATH), str)
            ):
                return path
        return None

    @cached_property
    @override
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        return set()

    @cached_property
    @override
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        return set()

    def _issue_id(self, entity_id: str) -> str:
        """Return the repair issue id for the entity_id."""
        return f"{entity_id}_validation_{self._validation_status}"

    @property
    def repair_issue_id(self) -> str:
        """Return the id of the repair issue."""
        return self._issue_id(self.entity_id)

    @callback
    def _async_create_issue(self) -> None:
        """Create a repair issue to notify the user the script has errors."""
        async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_id(self.entity_id),
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key=f"validation_{self._validation_status}",
            translation_placeholders={
                "edit": f"/config/script/edit/{self.unique_id}",
                "entity_id": self.entity_id,
                "error": self._validation_error,
                "name": self._attr_name or self.entity_id,
            },
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Create a repair issue to notify the user the script has errors."""
        await super().async_added_to_hass()
        self._async_create_issue()

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Move the repair issue, its id and placeholders use the entity_id."""
        super().async_entity_id_changed(old_entity_id)
        async_delete_issue(self.hass, DOMAIN, self._issue_id(old_entity_id))
        self._async_create_issue()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # A reload in progress keeps the issue if the new entity re-creates it
        async_delete_issue(
            self.hass, DOMAIN, self.repair_issue_id, defer_to_refresh=True
        )


class ScriptEntity(BaseScriptEntity, RestoreEntity):
    """Representation of a script entity."""

    icon = None
    _attr_should_poll = False
    _attr_unique_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        key: str,
        cfg: ConfigType,
        raw_config: ConfigType | None,
        blueprint_inputs: ConfigType | None,
    ) -> None:
        """Initialize the script."""
        self.icon = cfg.get(CONF_ICON)
        self.description = cfg[CONF_DESCRIPTION]
        self.fields = cfg[CONF_FIELDS]

        # The key of scripts are unique and cannot be changed from the UI after creating
        self._attr_unique_id = key

        self.entity_id = ENTITY_ID_FORMAT.format(key)
        self.script = Script(
            hass,
            cfg[CONF_SEQUENCE],
            cfg.get(CONF_ALIAS, key),
            DOMAIN,
            running_description="script sequence",
            change_listener=self.async_change_listener,
            script_mode=cfg[CONF_MODE],
            max_runs=cfg[CONF_MAX],
            max_exceeded=cfg[CONF_MAX_EXCEEDED],
            logger=logging.getLogger(f"{__package__}.{key}"),
            variables=cfg.get(CONF_VARIABLES),
        )
        self._changed = asyncio.Event()
        self.raw_config = raw_config
        self._trace_config = cfg[CONF_TRACE]
        self._blueprint_inputs = blueprint_inputs
        self._attr_name = self.script.name

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        script = self.script
        attrs = {
            ATTR_LAST_TRIGGERED: script.last_triggered,
            ATTR_MODE: script.script_mode,
            ATTR_CUR: script.runs,
        }
        if script.supports_max:
            attrs[ATTR_MAX] = script.max_runs
        if script.last_action:
            attrs[ATTR_LAST_ACTION] = script.last_action
        return attrs

    @property
    @override
    def is_on(self) -> bool:
        """Return true if script is on."""
        return self.script.is_running

    @cached_property
    @override
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        return self.script.referenced_labels

    @cached_property
    @override
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""
        return self.script.referenced_floors

    @cached_property
    @override
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        return self.script.referenced_areas

    @property
    @override
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        path: str = self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH]
        return path

    @cached_property
    @override
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        return self.script.referenced_devices

    @cached_property
    @override
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        return self.script.referenced_entities

    @callback
    def async_change_listener(self) -> None:
        """Update state."""
        self.async_write_ha_state()
        self._changed.set()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Run the script.

        Depending on the script's run mode, this may do nothing, restart the script or
        fire an additional parallel run.
        """
        variables: dict[str, Any] | None = kwargs.get("variables")
        context: Context = kwargs["context"]
        wait: bool = kwargs.get("wait", True)
        await self._async_start_run(variables, context, wait)

    async def _async_start_run(
        self, variables: dict[str, Any] | None, context: Context, wait: bool
    ) -> ServiceResponse:
        """Start the run of a script."""
        self.async_set_context(context)
        coro = self._async_run(variables, context)
        if wait:
            # If we are executing in parallel, we need to copy the script stack so
            # that if this script is called in parallel, it will not be seen in the
            # stack of the other parallel calls and hit the disallowed recursion
            # check as each parallel call would otherwise be appending to the same
            # stack. We do not wipe the stack in this case because we still want to
            # be able to detect if there is a disallowed recursion.
            if script_stack := script_stack_cv.get():
                script_stack_cv.set(script_stack.copy())

            script_result = await coro
            return script_result.service_response if script_result else None

        # Caller does not want to wait for called script to finish so let script run in
        # separate Task. Make a new empty script stack; scripts are allowed to
        # recursively turn themselves on when not waiting.
        script_stack_cv.set([])

        self._changed.clear()
        self.hass.async_create_task(coro, eager_start=True)
        # Wait for first state change so we can guarantee that
        # it is written to the State Machine before we return.
        await self._changed.wait()
        return None

    async def _async_run(
        self, variables: dict[str, Any] | None, context: Context
    ) -> ScriptRunResult | None:
        with trace_script(
            self.hass,
            self._attr_unique_id,
            self.raw_config,
            self._blueprint_inputs,
            context,
            self._trace_config,
        ) as script_trace:
            # Prepare tracing the execution of the script's sequence
            script_trace.set_trace(trace_get())
            self.hass.bus.async_fire(
                EVENT_SCRIPT_STARTED,
                {
                    ATTR_NAME: self.script.name,
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_ITEM_ID: self._attr_unique_id,
                    ATTR_RUN_ID: script_trace.run_id,
                },
                context=context,
            )
            with trace_path("sequence"):
                this = None
                if state := self.hass.states.get(self.entity_id):
                    this = state.as_dict()
                script_vars = {"this": this, **(variables or {})}
                return await self.script.async_run(script_vars, context)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop running the script.

        If multiple runs are in progress, all will be stopped.
        """
        await self.script.async_stop()

    async def _service_handler(self, service: ServiceCall) -> ServiceResponse:
        """Execute a service call to script.<script name>."""
        response = await self._async_start_run(
            variables=service.data, context=service.context, wait=True
        )
        if service.return_response:
            return response or {}
        return None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last triggered on startup and register service."""
        if TYPE_CHECKING:
            assert self.unique_id is not None
            assert self.registry_entry is not None

        unique_id = self.unique_id
        hass = self.hass
        # Cannot be moved: each script is also registered as its own action
        # pylint: disable-next=home-assistant-action-registered-outside-services-module
        hass.services.async_register(
            DOMAIN,
            unique_id,
            self._service_handler,
            schema=SCRIPT_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

        # Register the service description
        service_desc = {
            CONF_NAME: self.registry_entry.name or self.name,
            CONF_DESCRIPTION: self.description,
            CONF_FIELDS: self.fields,
        }
        async_set_service_schema(hass, DOMAIN, unique_id, service_desc)

        if (state := await self.async_get_last_state()) and (
            last_triggered := state.attributes.get("last_triggered")
        ):
            self.script.last_triggered = parse_datetime(last_triggered)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop script and remove service when it will be removed from HA."""
        self.hass.services.async_remove(DOMAIN, self._attr_unique_id)
        await self.script.async_unload()
