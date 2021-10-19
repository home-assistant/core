"""Config flow for Group integration."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.loader import async_get_integration

from . import PLATFORMS
from .const import DOMAIN


async def _async_name_to_type_map(hass: HomeAssistant) -> dict[str, str]:
    """Create a mapping of types of platforms group can support."""
    integrations = await asyncio.gather(
        *(async_get_integration(hass, domain) for domain in PLATFORMS),
        return_exceptions=True,
    )
    name_to_type_map = {
        domain: domain
        if isinstance(integrations[idx], Exception)
        else integrations[idx].name
        for idx, domain in enumerate(PLATFORMS)
    }
    return name_to_type_map


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Group."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.domain: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose specific domains in bridge mode."""
        if user_input is not None:
            self.domain = user_input[CONF_DOMAIN]
            return await self.async_step_entities()

        name_to_type_map = await _async_name_to_type_map(self.hass)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOMAIN): vol.In(name_to_type_map),
                }
            ),
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        assert self.domain is not None

        if user_input is not None:
            name_to_type_map = await _async_name_to_type_map(self.hass)
            domain_name = name_to_type_map[self.domain]
            return self.async_create_entry(
                title=f"{domain_name} Group",
                data={CONF_DOMAIN: self.domain},
                options=user_input,
            )

        domain_entities = _async_get_matching_entities(self.hass, [self.domain])
        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITIES): vol.In(domain_entities),
                }
            ),
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for group."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        domain = self.config_entry.data[CONF_DOMAIN]
        entities = self.config_entry.options[CONF_ENTITIES]
        domain_entities = _async_get_matching_entities(self.hass, [domain])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITIES, default=entities): vol.In(
                        domain_entities
                    ),
                }
            ),
        )


def _async_get_matching_entities(
    hass: HomeAssistant, domains: list[str]
) -> dict[str, str]:
    """Fetch all entities or entities in the given domains."""
    return {
        state.entity_id: f"{state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id)} ({state.entity_id})"
        for state in sorted(
            hass.states.async_all(domains and set(domains)),
            key=lambda item: item.entity_id,
        )
    }
