"""Config flow for the Dynamic DNS integration."""

from __future__ import annotations

from typing import Any

import dynamicdns
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_PROVIDER, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROVIDER): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        value=provider.value,
                        label=provider_conf.name,
                    )
                    for provider, provider_conf in dynamicdns.providers.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
                sort=True,
            )
        )
    }
)


class DynamicDnsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dynamic DNS."""

    provider: dynamicdns.Provider

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            self.provider = dynamicdns.Provider(user_input[CONF_PROVIDER])
            return self.async_show_form(
                step_id="params",
                data_schema=dynamicdns.providers[user_input[CONF_PROVIDER]].schema,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            last_step=False,
        )

    async def async_step_params(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second step."""

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            title = dynamicdns.providers[self.provider].name
            return self.async_create_entry(
                title=title, data={CONF_PROVIDER: self.provider.value, **user_input}
            )

        return self.async_show_form(
            step_id="params",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=dynamicdns.providers[self.provider].schema,
                suggested_values=user_input,
            ),
        )
