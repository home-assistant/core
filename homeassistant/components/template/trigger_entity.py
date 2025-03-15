"""Trigger entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import CONF_STATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import (
    _SENTINEL,
    TemplateStateFromEntityId,
    render_complex,
)
from homeassistant.helpers.trigger_template_entity import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    TriggerBaseEntity,
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
        AbstractTemplateEntity.__init__(self, hass)

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

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        return self.coordinator.referenced_blueprint

    @callback
    def _render_script_variables(self) -> dict:
        """Render configured variables."""
        return self.coordinator.data["run_variables"]

    @callback
    def _process_data(self) -> None:
        """Process new data."""

        run_variables = self.coordinator.data["run_variables"]
        variables = {
            "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            **(run_variables or {}),
        }

        self._render_templates(variables)

        self.async_set_context(self.coordinator.data["context"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._process_data()
        self.async_write_ha_state()

    def _render_single_template(
        self, key: str, variables: dict[str, Any], is_complex: bool
    ) -> Any:
        """Render a single template."""
        try:
            if is_complex:
                return render_complex(self._config[key], variables)

            return self._config[key].async_render(
                variables,
                parse_result=key in self._parse_result,
            )
        except TemplateError as err:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").error(
                "Error rendering %s template for %s: %s",
                key,
                self.entity_id,
                err,
            )

        return _SENTINEL

    def _render_templates(self, variables: dict[str, Any]) -> None:
        """Render templates."""
        rendered = dict(self._static_rendered)

        # Check availability first
        available = True
        if CONF_AVAILABILITY in self._to_render_simple:
            if (
                result := self._render_single_template(
                    CONF_AVAILABILITY, variables, False
                )
            ) is not _SENTINEL:
                rendered[CONF_AVAILABILITY] = available = result

        if not available:
            self._rendered = rendered
            return

        # If state fails to render, the entity should go unavailable.
        if CONF_STATE in self._to_render_simple:
            if (
                result := self._render_single_template(CONF_STATE, variables, False)
            ) is _SENTINEL:
                self._rendered = self._static_rendered
                return

            rendered[CONF_STATE] = result

        for key in self._to_render_simple:
            # Skip availability because we already handled it before.
            if key in (CONF_AVAILABILITY, CONF_STATE):
                continue

            if (
                result := self._render_single_template(key, variables, False)
            ) is not _SENTINEL:
                rendered[key] = result

        for key in self._to_render_complex:
            if (
                result := self._render_single_template(key, variables, True)
            ) is not _SENTINEL:
                rendered[key] = result

        if CONF_ATTRIBUTES in self._config:
            attributes = {}
            for attribute, attribute_template in self._config[CONF_ATTRIBUTES].items():
                try:
                    value = render_complex(attribute_template, variables)
                    attributes[attribute] = value
                    variables.update({attribute: value})
                except TemplateError as err:
                    logging.getLogger(
                        f"{__package__}.{self.entity_id.split('.')[0]}"
                    ).error(
                        "Error rendering %s.%s template for %s: %s",
                        CONF_ATTRIBUTES,
                        attribute,
                        self.entity_id,
                        err,
                    )
            rendered[CONF_ATTRIBUTES] = attributes

        self._rendered = rendered
