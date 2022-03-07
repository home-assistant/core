"""Config flow for Group integration."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import helper_config_entry_flow, selector

from . import DOMAIN


def basic_group_options_schema(domain: str) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_ENTITIES): selector.selector(
                {"entity": {"domain": domain, "multiple": True}}
            ),
        }
    )


def basic_group_config_schema(domain: str) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema({vol.Required("name"): selector.selector({"text": {}})}).extend(
        basic_group_options_schema(domain).schema
    )


STEPS = {
    "init": vol.Schema(
        {
            vol.Required("group_type"): selector.selector(
                {
                    "select": {
                        "options": [
                            "cover",
                            "fan",
                            "light",
                            "media_player",
                        ]
                    }
                }
            )
        }
    ),
    "cover": basic_group_config_schema("cover"),
    "fan": basic_group_config_schema("fan"),
    "light": basic_group_config_schema("light"),
    "media_player": basic_group_config_schema("media_player"),
    "cover_options": basic_group_options_schema("cover"),
    "fan_options": basic_group_options_schema("fan"),
    "light_options": basic_group_options_schema("light"),
    "media_player_options": basic_group_options_schema("media_player"),
}


class GroupConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Switch Light."""

    steps = STEPS

    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, user_input["name"]) if "name" in user_input else ""

    @staticmethod
    def async_initial_options_step(config_entry: ConfigEntry) -> str:
        """Return initial options step."""
        return f"{config_entry.options['group_type']}_options"

    def async_next_step(self, step_id: str, user_input: dict[str, Any]) -> str | None:
        """Return next step_id."""
        if step_id == "init":
            return cast(str, user_input["group_type"])
        return None

    async def async_validate_input(
        self, hass: HomeAssistant, step_id: str, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate user input."""
        if not self._config_entry:
            return user_input

        group_type = self._config_entry.options["group_type"]
        selected_entities = user_input[CONF_ENTITIES]
        return helper_config_entry_flow.async_own_entity_not_selected(
            hass, user_input, self._config_entry, group_type, DOMAIN, selected_entities
        )
