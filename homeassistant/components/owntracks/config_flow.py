"""Config flow for OwnTracks."""

import secrets

from homeassistant.components import cloud, webhook
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_WEBHOOK_ID

from .const import DOMAIN
from .helper import supports_encryption

CONF_SECRET = "secret"
CONF_CLOUDHOOK = "cloudhook"


class OwnTracksFlow(ConfigFlow, domain=DOMAIN):
    """Set up OwnTracks."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a user initiated set up flow to create OwnTracks webhook."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        try:
            webhook_id, webhook_url, cloudhook = await self._get_webhook_id()
        except cloud.CloudNotConnected:
            return self.async_abort(reason="cloud_not_connected")

        secret = secrets.token_hex(16)

        if supports_encryption():
            secret_desc = (
                f"The encryption key is {secret} (on Android under Preferences >"
                " Advanced)"
            )
        else:
            secret_desc = "Encryption is not supported because nacl is not installed."

        return self.async_create_entry(
            title="OwnTracks",
            data={
                CONF_WEBHOOK_ID: webhook_id,
                CONF_SECRET: secret,
                CONF_CLOUDHOOK: cloudhook,
            },
            description_placeholders={
                "secret": secret_desc,
                "webhook_url": webhook_url,
                "android_url": "https://play.google.com/store/apps/details?id=org.owntracks.android",
                "ios_url": "https://itunes.apple.com/us/app/owntracks/id692424691?mt=8",
                "docs_url": "https://www.home-assistant.io/integrations/owntracks/",
            },
        )

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
