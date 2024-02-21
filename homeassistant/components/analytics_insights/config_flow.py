"""Config flow for Homeassistant Analytics integration."""
from __future__ import annotations

from typing import Any

from python_homeassistant_analytics import (
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
)
from python_homeassistant_analytics.models import IntegrationType
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_TRACKED_CUSTOM_INTEGRATIONS,
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
    LOGGER,
)

INTEGRATION_TYPES_WITHOUT_ANALYTICS = (
    IntegrationType.BRAND,
    IntegrationType.ENTITY,
    IntegrationType.VIRTUAL,
)


class HomeassistantAnalyticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeassistant Analytics."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return HomeassistantAnalyticsOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._async_abort_entries_match()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_TRACKED_INTEGRATIONS) and not user_input.get(
                CONF_TRACKED_CUSTOM_INTEGRATIONS
            ):
                errors["base"] = "no_integrations_selected"
            else:
                return self.async_create_entry(
                    title="Home Assistant Analytics Insights",
                    data={},
                    options={
                        CONF_TRACKED_INTEGRATIONS: user_input.get(
                            CONF_TRACKED_INTEGRATIONS, []
                        ),
                        CONF_TRACKED_CUSTOM_INTEGRATIONS: user_input.get(
                            CONF_TRACKED_CUSTOM_INTEGRATIONS, []
                        ),
                    },
                )

        client = HomeassistantAnalyticsClient(
            session=async_get_clientsession(self.hass)
        )
        try:
            integrations = await client.get_integrations()
            custom_integrations = await client.get_custom_integrations()
        except HomeassistantAnalyticsConnectionError:
            LOGGER.exception("Error connecting to Home Assistant analytics")
            return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(
                value=domain,
                label=integration.title,
            )
            for domain, integration in integrations.items()
            if integration.integration_type not in INTEGRATION_TYPES_WITHOUT_ANALYTICS
        ]
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TRACKED_INTEGRATIONS): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            sort=True,
                        )
                    ),
                    vol.Optional(CONF_TRACKED_CUSTOM_INTEGRATIONS): SelectSelector(
                        SelectSelectorConfig(
                            options=list(custom_integrations),
                            multiple=True,
                            sort=True,
                        )
                    ),
                }
            ),
        )


class HomeassistantAnalyticsOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle Homeassistant Analytics options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_TRACKED_INTEGRATIONS) and not user_input.get(
                CONF_TRACKED_CUSTOM_INTEGRATIONS
            ):
                errors["base"] = "no_integrations_selected"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_TRACKED_INTEGRATIONS: user_input.get(
                            CONF_TRACKED_INTEGRATIONS, []
                        ),
                        CONF_TRACKED_CUSTOM_INTEGRATIONS: user_input.get(
                            CONF_TRACKED_CUSTOM_INTEGRATIONS, []
                        ),
                    },
                )

        client = HomeassistantAnalyticsClient(
            session=async_get_clientsession(self.hass)
        )
        try:
            integrations = await client.get_integrations()
            custom_integrations = await client.get_custom_integrations()
        except HomeassistantAnalyticsConnectionError:
            LOGGER.exception("Error connecting to Home Assistant analytics")
            return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(
                value=domain,
                label=integration.title,
            )
            for domain, integration in integrations.items()
            if integration.integration_type not in INTEGRATION_TYPES_WITHOUT_ANALYTICS
        ]
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_TRACKED_INTEGRATIONS): SelectSelector(
                            SelectSelectorConfig(
                                options=options,
                                multiple=True,
                                sort=True,
                            )
                        ),
                        vol.Optional(CONF_TRACKED_CUSTOM_INTEGRATIONS): SelectSelector(
                            SelectSelectorConfig(
                                options=list(custom_integrations),
                                multiple=True,
                                sort=True,
                            )
                        ),
                    },
                ),
                self.options,
            ),
        )
