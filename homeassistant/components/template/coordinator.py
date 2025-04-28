"""Data update coordinator for trigger based template entities."""

from collections.abc import Callable, Mapping
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import CONF_PATH, CONF_VARIABLES, EVENT_HOMEASSISTANT_START
from homeassistant.core import Context, CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import condition, discovery, trigger as trigger_helper
from homeassistant.helpers.script import Script
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.trace import trace_get
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ACTION, CONF_CONDITION, CONF_TRIGGER, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class TriggerUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for trigger based template entities."""

    REMOVE_TRIGGER = object()

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Instantiate trigger data."""
        super().__init__(
            hass, _LOGGER, config_entry=None, name="Trigger Update Coordinator"
        )
        self.config = config
        self._cond_func: Callable[[Mapping[str, Any] | None], bool] | None = None
        self._unsub_start: Callable[[], None] | None = None
        self._unsub_trigger: Callable[[], None] | None = None
        self._script: Script | None = None
        self._run_variables: ScriptVariables | None = None
        self._blueprint_inputs: dict | None = None
        if config is not None:
            self._run_variables = config.get(CONF_VARIABLES)
            self._blueprint_inputs = getattr(config, "raw_blueprint_inputs", None)

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    @property
    def unique_id(self) -> str | None:
        """Return unique ID for the entity."""
        return self.config.get("unique_id")

    @callback
    def async_remove(self) -> None:
        """Signal that the entities need to remove themselves."""
        if self._unsub_start:
            self._unsub_start()
        if self._unsub_trigger:
            self._unsub_trigger()

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
        if CONF_ACTION in self.config:
            self._script = Script(
                self.hass,
                self.config[CONF_ACTION],
                self.name,
                DOMAIN,
            )

        if CONF_CONDITION in self.config:
            self._cond_func = await condition.async_conditions_from_config(
                self.hass, self.config[CONF_CONDITION], _LOGGER, "template entity"
            )

        if start_event is not None:
            self._unsub_start = None

        if self._script:
            action: Callable = self._handle_triggered_with_script
        else:
            action = self._handle_triggered

        self._unsub_trigger = await trigger_helper.async_initialize_triggers(
            self.hass,
            self.config[CONF_TRIGGER],
            action,
            DOMAIN,
            self.name,
            self.logger.log,
            start_event is not None,
        )

    async def _handle_triggered_with_script(
        self, run_variables: TemplateVarsType, context: Context | None = None
    ) -> None:
        # Render run variables after the trigger, before checking conditions.
        if self._run_variables:
            run_variables = self._run_variables.async_render(self.hass, run_variables)

        if not self._check_condition(run_variables):
            return
        # Create a context referring to the trigger context.
        trigger_context_id = None if context is None else context.id
        script_context = Context(parent_id=trigger_context_id)
        if TYPE_CHECKING:
            # This method is only called if there's a script
            assert self._script is not None
        if script_result := await self._script.async_run(run_variables, script_context):
            run_variables = script_result.variables
        self._execute_update(run_variables, context)

    async def _handle_triggered(
        self, run_variables: TemplateVarsType, context: Context | None = None
    ) -> None:
        if self._run_variables:
            run_variables = self._run_variables.async_render(self.hass, run_variables)

        if not self._check_condition(run_variables):
            return
        self._execute_update(run_variables, context)

    def _check_condition(self, run_variables: TemplateVarsType) -> bool:
        if not self._cond_func:
            return True
        condition_result = self._cond_func(run_variables)
        if condition_result is False:
            _LOGGER.debug(
                "Conditions not met, aborting template trigger update. Condition summary: %s",
                trace_get(clear=False),
            )
        return condition_result

    @callback
    def _execute_update(
        self, run_variables: TemplateVarsType, context: Context | None = None
    ) -> None:
        self.async_set_updated_data(
            {"run_variables": run_variables, "context": context}
        )
