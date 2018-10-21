"""Helpers for data entry flows for config entries that use webhooks."""
from functools import partial
from urllib.parse import urlparse

from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.util.network import is_local


def register_webhook_flow(domain, title, description_placeholder):
    """Register flow for webhook integrations.."""
    config_entries.HANDLERS.register(domain)(
        partial(WebhookFlowHandler, domain, title, description_placeholder))


class WebhookFlowHandler(config_entries.ConfigFlow):
    """Handle a webhook config flow."""

    VERSION = 1

    def __init__(self, domain, title, description_placeholder,
                 allow_multiple=False):
        """Initialize the discovery config flow."""
        self._domain = domain
        self._title = title
        self._description_placeholder = description_placeholder
        self._allow_multiple = allow_multiple

    async def async_step_user(self, user_input=None):
        """Handle a user initiated set up flow to create a webhook."""
        if not self._allow_multiple and self._async_current_entries():
            return self.async_abort(reason='one_instance_allowed')

        try:
            url_parts = urlparse(self.hass.config.api.base_url)

            if is_local(ip_address(url_parts.hostname)):
                return self.async_abort(reason='not_internet_accessible')
        except ValueError:
            # If it's not an IP address, it's very likely publicly accessible
            pass

        if user_input is None:
            return self.async_show_form(
                step_id='user',
            )

        webhook_id = self.hass.components.webhook.async_generate_id()
        webhook_url = \
            self.hass.components.webhook.async_generate_url(webhook_id)

        self._description_placeholder['webhook_url'] = webhook_url

        return self.async_create_entry(
            title=self._title,
            data={
                'webhook_id': webhook_id
            },
            description_placeholders=self._description_placeholder
        )
