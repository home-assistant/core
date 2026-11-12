"""Data update coordinator for trigger based template entities."""

from collections.abc import Callable, Mapping
import logging
from typing import TYPE_CHECKING, Any, TypedDict, cast, override

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import (
    CONF_ACTIONS,
    CONF_CONDITIONS,
    CONF_PATH,
    CONF_TRIGGERS,
    CONF_VARIABLES,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import Context, CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import condition, discovery, trigger as trigger_helper
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_TRIGGER_VARIABLES, DOMAIN, PLATFORMS
from .validators import check_conditions, entity_config_identifier

_LOGGER = logging.getLogger(__name__)


class TriggerData(TypedDict):
    """Data of a trigger update."""

    run_variables: Mapping[str, Any]
    context: Context | None


class TriggerUpdateCoordinator(DataUpdateCoordinator[TriggerData]):
    """Data update coordinator for trigger based template entities."""

    REMOVE_TRIGGER = object()

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Instantiate trigger data."""
        super().__init__(
            hass, _LOGGER, config_entry=None, name="Trigger Update Coordinator"
        )
        self.config = config
        self._cond_func: condition.ConditionsChecker | None = None
        self._unsub_start: Callable[[], None] | None = None
        self._unsub_trigger: Callable[[], None] | None = None
        self._script: Script | None = None
        self._run_variables: ScriptVariables | None = None
        self._trigger_variables: ScriptVariables | None = None
        self._rendered_trigger_variables: dict[str, Any] = {}
        self._blueprint_inputs: dict | None = None
        self.entities: set[Entity] = set()
        if config is not None:
            self._trigger_variables = config.get(CONF_TRIGGER_VARIABLES)
            self._run_variables = config.get(CONF_VARIABLES)
            self._blueprint_inputs = getattr(config, "raw_blueprint_inputs", None)

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    @property
    def trigger_variables(self) -> dict[str, Any]:
        """Return the rendered trigger variables."""
        return self._rendered_trigger_variables

    @property
    def unique_id(self) -> str | None:
        """Return unique ID for the entity."""
        return self.config.get("unique_id")

    @override
    async def async_shutdown(self) -> None:
        """Shut down the coordinator and clean up resources."""
        await super().async_shutdown()
        if self._unsub_start:
            self._unsub_start()
            self._unsub_start = None
        if self._unsub_trigger:
            self._unsub_trigger()
            self._unsub_trigger = None
        if self._script is not None:
            await self._script.async_unload()
        if self._cond_func is not None:
            self._cond_func.async_unload()

    async def async_setup(self, hass_config: ConfigType) -> None:
        """Set up the trigger and create entities."""
        if self.hass.state is CoreState.running:
            await self._attach_triggers()
        else:
            self._unsub_start = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, self._attach_triggers
            )

        for platform_domain in PLATFORMS:
            if platform_domain in self.config:
                self.hass.async_create_task(
                    discovery.async_load_platform(
                        self.hass,
                        platform_domain,
                        DOMAIN,
                        {"coordinator": self, "entities": self.config[platform_domain]},
                        hass_config,
                    ),
                    eager_start=True,
                )

    async def _attach_triggers(self, start_event: Event | None = None) -> None:
        """Attach the triggers."""
        if CONF_ACTIONS in self.config:
            self._script = Script(
                self.hass,
                self.config[CONF_ACTIONS],
                self.name,
                DOMAIN,
            )

        if CONF_CONDITIONS in self.config:
            self._cond_func = await condition.async_conditions_from_config(
                self.hass, self.config[CONF_CONDITIONS], _LOGGER, "template entity"
            )

        if start_event is not None:
            self._unsub_start = None

        if self._script:
            action: Callable = self._handle_triggered_with_script
        else:
            action = self._handle_triggered

        if self._trigger_variables:
            try:
                self._rendered_trigger_variables = self._trigger_variables.async_render(
                    self.hass, None, limited=True
                )
            except TemplateError as err:
                self.logger.error("Error rendering trigger variables: %s", err)
                return

        self._unsub_trigger = await trigger_helper.async_initialize_triggers(
            self.hass,
            self.config[CONF_TRIGGERS],
            action,
            DOMAIN,
            self.name,
            self.logger.log,
            variables=self._rendered_trigger_variables,
        )

    @callback
    def _render_run_variables(self, run_variables: TemplateVarsType) -> dict[str, Any]:
        """Render run variables after the trigger, before checking conditions."""
        run_variables = run_variables or {}
        variables = {**self._rendered_trigger_variables, **run_variables}
        if not self._run_variables:
            return variables
        # Trigger variables can be overridden but trigger data can't, so drop
        # variables that collide with trigger data before rendering.
        section = self._run_variables
        if not run_variables.keys().isdisjoint(section.as_dict()):
            section = ScriptVariables(
                {
                    key: value
                    for key, value in section.as_dict().items()
                    if key not in run_variables
                }
            )
        variables.update(section.async_simple_render(variables))
        return variables

    @callback
    def _async_render_variables_and_conditions(
        self, run_variables: TemplateVarsType
    ) -> Mapping[str, Any] | None:
        """Render run variables and check conditions, None means stop."""
        try:
            run_variables = self._render_run_variables(run_variables)
        except TemplateError as err:
            entities = sorted(entity.entity_id for entity in self.entities) or [
                entity_config_identifier(platform_domain, entity_config)
                for platform_domain in PLATFORMS
                for entity_config in self.config.get(platform_domain, [])
            ]
            if entities:
                self.logger.error(
                    "Error rendering variables for %s: %s", ", ".join(entities), err
                )
            else:
                self.logger.error("Error rendering variables: %s", err)
            return None
        if not check_conditions(self._cond_func, run_variables):
            return None
        return run_variables

    async def _handle_triggered_with_script(
        self, run_variables: TemplateVarsType, context: Context | None = None
    ) -> None:
        if (
            run_variables := self._async_render_variables_and_conditions(run_variables)
        ) is None:
            return
        # Create a context referring to the trigger context.
        trigger_context_id = None if context is None else context.id
        script_context = Context(parent_id=trigger_context_id)
        if TYPE_CHECKING:
            # This method is only called if there's a script
            assert self._script is not None

        if script_result := await self._script.async_run(run_variables, script_context):
            self._execute_update(script_result.variables, context)

    async def _handle_triggered(
        self, run_variables: TemplateVarsType, context: Context | None = None
    ) -> None:
        if (
            run_variables := self._async_render_variables_and_conditions(run_variables)
        ) is None:
            return
        self._execute_update(run_variables, context)

    @callback
    def _execute_update(
        self, run_variables: Mapping[str, Any], context: Context | None = None
    ) -> None:
        self.async_set_updated_data(
            {"run_variables": run_variables, "context": context}
        )
