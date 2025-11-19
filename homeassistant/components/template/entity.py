"""Template entity base class."""

from abc import abstractmethod
import logging

from homeassistant.const import CONF_DEVICE_ID, CONF_OPTIMISTIC, CONF_STATE
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.script import (
    Script,
    _VarsType,
    async_validate_actions_config,
)
from homeassistant.helpers.template import Template, TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEFAULT_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TemplateActions:
    """Scripts for template entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        config: list[ConfigType],
    ) -> None:
        """Initialize the template script."""
        self.hass = hass
        self.name = name
        self.config = config
        self.script: Script | None = None

    async def validate_actions_and_create_script(self) -> None:
        """Validate actions and create the script."""
        self.config = await async_validate_actions_config(self.hass, self.config)
        self.script = Script(
            self.hass,
            self.config,
            self.name,
            DOMAIN,
        )

    async def run(self, run_variables: _VarsType, context: Context | None) -> None:
        """Run the actions."""
        if self.script:
            await self.script.async_run(run_variables=run_variables, context=context)


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    _entity_id_format: str
    _optimistic_entity: bool = False
    _extra_optimistic_options: tuple[str, ...] | None = None
    _template: Template | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""

        self.hass = hass
        self._is_preview_entity: bool = config.get("__is_preview_entity", False)
        self._action_scripts: dict[str, TemplateActions] = {}

        if self._optimistic_entity:
            optimistic = config.get(CONF_OPTIMISTIC)

            self._template = config.get(CONF_STATE)

            assumed_optimistic = self._template is None
            if self._extra_optimistic_options:
                assumed_optimistic = assumed_optimistic and all(
                    config.get(option) is None
                    for option in self._extra_optimistic_options
                )

            self._attr_assumed_state = optimistic or (
                optimistic is None and assumed_optimistic
            )

        if (default_entity_id := config.get(CONF_DEFAULT_ENTITY_ID)) is not None:
            _, _, object_id = default_entity_id.partition(".")
            self.entity_id = async_generate_entity_id(
                self._entity_id_format, object_id, hass=self.hass
            )

        device_registry = dr.async_get(hass)
        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            self.device_entry = device_registry.async_get(device_id)

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @callback
    @abstractmethod
    def _render_script_variables(self) -> dict:
        """Render configured variables."""

    def add_actions(
        self,
        script_id: str,
        config: list[ConfigType],
        name: str,
    ):
        """Add an action script."""
        self._action_scripts[script_id] = TemplateActions(
            self.hass, f"{name} {script_id}", config
        )

    async def async_setup_actions(self) -> None:
        """Setup template actions."""
        if not self._is_preview_entity:
            for action in self._action_scripts.values():
                await action.validate_actions_and_create_script()

    async def async_run_actions(
        self,
        actions: TemplateActions,
        *,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
    ) -> None:
        """Run an action script."""
        if run_variables is None:
            run_variables = {}
        await actions.run(
            {
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
                **self._render_script_variables(),
                **run_variables,
            },
            context,
        )
