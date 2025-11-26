"""Trigger entity."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import CONF_STATE, CONF_VARIABLES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import _SENTINEL
from homeassistant.helpers.trigger_template_entity import TriggerBaseEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity


class TriggerEntity(  # pylint: disable=hass-enforce-class-module
    TriggerBaseEntity,
    CoordinatorEntity[TriggerUpdateCoordinator],
    AbstractTemplateEntity,
):
    """Template entity based on trigger data."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        CoordinatorEntity.__init__(self, coordinator)
        TriggerBaseEntity.__init__(self, hass, config)
        AbstractTemplateEntity.__init__(self, hass, config)

        self._entity_variables: ScriptVariables | None = config.get(CONF_VARIABLES)
        self._rendered_entity_variables: dict | None = None
        self._state_render_error = False

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._process_data()

    def _set_unique_id(self, unique_id: str | None) -> None:
        """Set unique id."""
        if unique_id and self.coordinator.unique_id:
            self._unique_id = f"{self.coordinator.unique_id}-{unique_id}"
        else:
            self._unique_id = unique_id

    def setup_state_template(
        self,
        option: str,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
    ) -> None:
        """Set up a template that manages the main state of the entity."""
        if self._config.get(option):
            self._to_render_simple.append(CONF_STATE)
            self._parse_result.add(CONF_STATE)
            self.add_template(option, attribute, validator, on_update)

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        return self.coordinator.referenced_blueprint

    @property
    def available(self) -> bool:
        """Return availability of the entity."""
        if self._state_render_error:
            return False

        return super().available

    @callback
    def _render_script_variables(self) -> dict:
        """Render configured variables."""
        return self._rendered_entity_variables or {}

    def _render_templates(self, variables: dict[str, Any]) -> None:
        """Render templates."""
        self._state_render_error = False
        rendered = dict(self._static_rendered)

        # If state fails to render, the entity should go unavailable. Render the
        # state as a simple template because the result should always be a string or None.
        if CONF_STATE in self._to_render_simple:
            if (
                result := self._render_single_template(CONF_STATE, variables)
            ) is _SENTINEL:
                self._rendered = self._static_rendered
                self._state_render_error = True
                return

            rendered[CONF_STATE] = result

        self._render_single_templates(rendered, variables, [CONF_STATE])
        self._render_attributes(rendered, variables)
        self._rendered = rendered

    def handle_rendered_result(self, key: str) -> bool:
        """Get a rendered result and return the value."""
        if (rendered := self._rendered.get(key)) is not None:
            if (entity_template := self._templates.get(key)) is not None:
                value = rendered
                if entity_template.validator:
                    value = entity_template.validator(rendered)

                if entity_template.on_update:
                    entity_template.on_update(value)
                else:
                    setattr(self, entity_template.attribute, value)

                return True

        return False

    @callback
    def _process_data(self) -> None:
        """Process new data."""

        coordinator_variables = self.coordinator.data["run_variables"]
        if self._entity_variables:
            entity_variables = self._entity_variables.async_simple_render(
                coordinator_variables
            )
            self._rendered_entity_variables = {
                **coordinator_variables,
                **entity_variables,
            }
        else:
            self._rendered_entity_variables = coordinator_variables
        variables = self._template_variables(self._rendered_entity_variables)
        if self._render_availability_template(variables):
            self._render_templates(variables)

        self.async_set_context(self.coordinator.data["context"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._process_data()
        self.async_write_ha_state()
