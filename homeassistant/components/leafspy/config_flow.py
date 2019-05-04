"""Config flow for Leaf Spy."""
import re

from homeassistant import config_entries
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.auth.util import generate_secret


from .const import (URL_LEAFSPY_PATH, CONF_SECRET, DOMAIN)


@config_entries.HANDLERS.register(DOMAIN)
class LeafSpyFlow(config_entries.ConfigFlow):
    """Set up Leaf Spy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a user initiated set up flow to create Leaf Spy webhook."""
        if self._async_current_entries():
            return self.async_abort(reason='one_instance_allowed')

        if user_input is None:
            return self.async_show_form(
                step_id='user',
            )

        secret = generate_secret(8)

        url = "{}{}".format(self.hass.config.api.base_url, URL_LEAFSPY_PATH)
        url = re.sub(r"https?://", "", url)

        return self.async_create_entry(
            title="Leaf Spy",
            data={
                CONF_SECRET: secret
            },
            description_placeholders={
                'secret': secret,
                'url': url,
                'docs_url': 'https://www.home-assistant.io/components/leafspy/'
            }
        )
