"""Config flow for proximity."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_ZONE
from homeassistant.core import State, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
)
from homeassistant.util import slugify

from .const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DEFAULT_PROXIMITY_ZONE,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

RESULT_SUCCESS = "success"


def _base_schema(user_input: dict[str, Any]) -> vol.Schema:
    return {
        vol.Required(
            CONF_TRACKED_ENTITIES, default=user_input.get(CONF_TRACKED_ENTITIES, [])
        ): EntitySelector(
            EntitySelectorConfig(
                domain=[DEVICE_TRACKER_DOMAIN, PERSON_DOMAIN], multiple=True
            ),
        ),
        vol.Optional(
            CONF_IGNORED_ZONES, default=user_input.get(CONF_IGNORED_ZONES, [])
        ): EntitySelector(
            EntitySelectorConfig(domain=ZONE_DOMAIN, multiple=True),
        ),
        vol.Required(
            CONF_TOLERANCE,
            default=user_input.get(CONF_TOLERANCE, DEFAULT_TOLERANCE),
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=100, step=1),
        ),
    }


class ProximityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a proximity config flow."""

    VERSION = 1

    def _user_form_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        if user_input is None:
            user_input = {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_ZONE,
                    default=user_input.get(
                        CONF_ZONE, f"{ZONE_DOMAIN}.{DEFAULT_PROXIMITY_ZONE}"
                    ),
                ): EntitySelector(
                    EntitySelectorConfig(domain=ZONE_DOMAIN),
                ),
                **_base_schema(user_input),
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ProximityOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            title = cast(State, self.hass.states.get(user_input[CONF_ZONE])).name

            slugified_existing_entry_titles = [
                slugify(e.title) for e in self._async_current_entries()
            ]

            possible_title = title
            tries = 1
            while slugify(possible_title) in slugified_existing_entry_titles:
                tries += 1
                possible_title = f"{title} {tries}"

            return self.async_create_entry(title=possible_title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_form_schema(user_input),
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import a yaml config entry."""
        return await self.async_step_user(user_input)


class ProximityOptionsFlow(OptionsFlow):
    """Handle a option flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    def _user_form_schema(self, user_input: dict[str, Any]) -> vol.Schema:
        return vol.Schema(_base_schema(user_input))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, **user_input}
            )
            return self.async_create_entry(title=self.config_entry.title, data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self._user_form_schema(dict(self.config_entry.data)),
        )
