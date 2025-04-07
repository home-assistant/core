"""Repairs implementation for the cloud integration."""

from __future__ import annotations

from typing import cast

import voluptuous as vol

from homeassistant.components.assist_satellite import DOMAIN as ASSIST_SATELLITE_DOMAIN
from homeassistant.components.repairs import RepairsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

REQUIRED_KEYS = ("entity_id", "entity_uuid", "integration_name")


class AssistInProgressDeprecatedRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str | int | float | None] | None) -> None:
        """Initialize."""
        if not data or any(key not in data for key in REQUIRED_KEYS):
            raise ValueError("Missing data")
        self._data = data

    async def async_step_init(self, _: None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm_disable_entity()

    async def async_step_confirm_disable_entity(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entity_registry = er.async_get(self.hass)
            entity_entry = entity_registry.async_get(
                cast(str, self._data["entity_uuid"])
            )
            if entity_entry:
                entity_registry.async_update_entity(
                    entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
                )
            return self.async_create_entry(data={})

        description_placeholders: dict[str, str] = {
            "assist_satellite_domain": ASSIST_SATELLITE_DOMAIN,
            "entity_id": cast(str, self._data["entity_id"]),
            "integration_name": cast(str, self._data["integration_name"]),
        }
        return self.async_show_form(
            step_id="confirm_disable_entity",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )
