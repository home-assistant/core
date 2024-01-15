"""Config flow for Homeassistant Analytics integration."""
from __future__ import annotations

from typing import Any

from python_homeassistant_analytics import (
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_TRACKED_INTEGRATIONS, DOMAIN, LOGGER


class HomeassistantAnalyticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeassistant Analytics."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._async_abort_entries_match()
        if user_input:
            return self.async_create_entry(
                title="Home Assistant analytics", data={}, options=user_input
            )

        client = HomeassistantAnalyticsClient(
            session=async_get_clientsession(self.hass)
        )
        try:
            analytics = await client.get_current_analytics()
            integrations = await client.get_integrations()
        except HomeassistantAnalyticsConnectionError:
            LOGGER.exception("Error connecting to Home Assistant analytics")
            return self.async_abort(reason="cannot_connect")

        def get_integration_name(integration: str) -> str:
            """Return the name of an integration or the domain if not found."""
            if integration in integrations:
                return integrations[integration].title
            return integration

        options = [
            SelectOptionDict(
                value=integration,
                label=get_integration_name(integration),
            )
            for integration in analytics.integrations
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRACKED_INTEGRATIONS): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            sort=True,
                        )
                    ),
                }
            ),
        )
