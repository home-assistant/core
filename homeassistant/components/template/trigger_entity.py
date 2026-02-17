"""Trigger entity."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import CONF_STATE, CONF_VARIABLES
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import (
    _SENTINEL,
    render_complex as template_render_complex,
)
from homeassistant.helpers.trigger_template_entity import (
    TriggerBaseEntity,
    log_triggered_template_error,
)
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
        if self.add_template(
            option, attribute, validator, on_update, none_on_template_error=False
        ):
            self._to_render_simple.append(option)
            self._parse_result.add(option)

    def setup_template(
        self,
        option: str,
        attribute: str,
        validator: Callable[[Any], Any] | None = None,
        on_update: Callable[[Any], None] | None = None,
        render_complex: bool = False,
        none_on_template_error: bool = True,
    ) -> None:
        """Set up a template that manages any property or attribute of the entity.

        Parameters
        ----------
        option
            The configuration key provided by ConfigFlow or the yaml option
        attribute
            The name of the attribute to link to. This attribute must exist
            unless a custom on_update method is supplied.
        validator:
            Optional function that validates the rendered result.
        on_update:
            Called to store the template result rather than storing it
            the supplied attribute. Passed the result of the validator.
        render_complex (default=False):
            This signals trigger based template entities to render the template
            as a complex result. State based template entities always render
            complex results.
        none_on_template_error (default=True)
            If set to false, template errors will be supplied in the result to
            on_update.
        """
        if self.add_template(
            option, attribute, validator, on_update, none_on_template_error
        ):
            if render_complex:
                self._to_render_complex.append(option)
            else:
                self._to_render_simple.append(option)
            self._parse_result.add(option)

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

    def _render_single_template(
        self,
        key: str,
        variables: dict[str, Any],
        strict: bool = False,
    ) -> Any:
        """Render a single template."""
        try:
            if key in self._to_render_complex:
                return template_render_complex(self._config[key], variables)

            return self._config[key].async_render(
                variables, parse_result=key in self._parse_result, strict=strict
            )
        except TemplateError as err:
            log_triggered_template_error(self.entity_id, err, key=key)
            # Filter out state templates because they have unique behavior
            # with none_on_template_error.
            if (
                key != CONF_STATE
                and key in self._templates
                and not self._templates[key].none_on_template_error
            ):
                return err

        return _SENTINEL

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

    def _handle_rendered_results(self) -> bool:
        """Get a rendered result and return the value."""
        # Handle any templates.
        write_state = False
        for option, entity_template in self._templates.items():
            # Capture templates that did not render a result due to an exception and
            # ensure the state object updates. _SENTINEL is used to differentiate
            # templates that render None.
            if (rendered := self._rendered.get(option, _SENTINEL)) is _SENTINEL:
                write_state = True
                continue

            value = (
                entity_template.validator(rendered)
                if entity_template.validator
                else rendered
            )

            if entity_template.on_update:
                entity_template.on_update(value)
            else:
                setattr(self, entity_template.attribute, value)
            write_state = True

        return write_state

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

        self.async_set_context(self.coordinator.data["context"])
        if self._render_availability_template(variables):
            self._render_templates(variables)

            write_state = False
            # While transitioning platforms to the new framework, this
            # if-statement is necessary for backward compatibility with existing
            # trigger based platforms.
            if self._templates:
                # Handle any results that were rendered.
                write_state = self._handle_rendered_results()

            # Check availability after rendering the results because the state
            # template could render the entity unavailable
            if not self.available:
                write_state = True

            if len(self._rendered) > 0:
                # In some cases, the entity may be state optimistic or
                # attribute optimistic, in these scenarios the state needs
                # to update.
                write_state = True

            if write_state:
                self.async_write_ha_state()
        else:
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        While transitioning platforms to the new framework, this
        function is necessary for backward compatibility with existing
        trigger based platforms.
        """
        self._process_data()
