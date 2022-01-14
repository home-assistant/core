"""Config flow to configure the Open-Meteo integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN, ENTITY_ID_HOME
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ZONE
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class OpenMeteoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for OpenMeteo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        zones: dict[str, str] = {
            entity_id: state.name
            for entity_id in self.hass.states.async_entity_ids(ZONE_DOMAIN)
            if (state := self.hass.states.get(entity_id)) is not None
        }

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ZONE])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=zones[user_input[CONF_ZONE]],
                data={CONF_ZONE: user_input[CONF_ZONE]},
            )

        zones = dict(sorted(zones.items(), key=lambda x: x[1], reverse=True))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE): vol.In(
                        {
                            ENTITY_ID_HOME: zones.pop(ENTITY_ID_HOME),
                            **zones,
                        }
                    ),
                }
            ),
        )
