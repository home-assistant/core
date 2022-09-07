"""Config flow for Twilio integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import cloud, webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_ACCOUNT_SID, CONF_AUTH_TOKEN, CONF_CLOUDHOOK, DOMAIN

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_SID): selector.TextSelector(),
        vol.Required(CONF_AUTH_TOKEN): selector.TextSelector(),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twilio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

        try:
            webhook_id, webhook_url, cloudhook = await self._get_webhook_id()
        except cloud.CloudNotConnected:
            return self.async_abort(reason="cloud_not_connected")

        user_input[CONF_WEBHOOK_ID] = webhook_id
        user_input[CONF_CLOUDHOOK] = cloudhook

        return self.async_create_entry(
            title="Twilio",
            data=user_input,
            description_placeholders={
                "webhook_url": webhook_url,
                "twilio_url": "https://www.twilio.com/docs/glossary/what-is-a-webhook",
                "docs_url": "https://www.home-assistant.io/integrations/twilio/",
            },
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""

        if self._async_current_entries():
            # an entry exists for the webhook so just save the
            # account_sid and auth_token in data
            entry = self._async_current_entries()[0]
            data = {
                **entry.data,
                CONF_ACCOUNT_SID: import_config[CONF_ACCOUNT_SID],
                CONF_AUTH_TOKEN: import_config[CONF_AUTH_TOKEN],
            }
            self.hass.config_entries.async_update_entry(entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)

    async def _get_webhook_id(self):
        """Generate webhook ID."""
        webhook_id = webhook.async_generate_id()
        if cloud.async_active_subscription(self.hass):
            webhook_url = await cloud.async_create_cloudhook(self.hass, webhook_id)
            cloudhook = True
        else:
            webhook_url = webhook.async_generate_url(self.hass, webhook_id)
            cloudhook = False

        return webhook_id, webhook_url, cloudhook

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TwilioOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TwilioOptionsFlowHandler(config_entry)


class TwilioOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Twilio."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        if user_input is not None:
            return self.async_create_entry(title="", data={})

        webhook_id = self.config_entry.data[CONF_WEBHOOK_ID]
        webhook_url = webhook.async_generate_url(self.hass, webhook_id)

        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "webhook_url": webhook_url,
                "twilio_url": "https://www.twilio.com/docs/glossary/what-is-a-webhook",
                "docs_url": "https://www.home-assistant.io/integrations/twilio/",
            },
        )
