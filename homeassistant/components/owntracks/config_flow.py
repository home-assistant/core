"""Config flow for OwnTracks."""
from homeassistant import config_entries
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.auth.util import generate_secret

CONF_SECRET = 'secret'


def supports_encryption():
    """Test if we support encryption."""
    try:
        # pylint: disable=unused-variable
        import libnacl   # noqa
        return True
    except OSError:
        return False


@config_entries.HANDLERS.register('owntracks')
class OwnTracksFlow(config_entries.ConfigFlow):
    """Set up OwnTracks."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a user initiated set up flow to create OwnTracks webhook."""
        if self._async_current_entries():
            return self.async_abort(reason='one_instance_allowed')

        if user_input is None:
            return self.async_show_form(
                step_id='user',
            )

        webhook_id = self.hass.components.webhook.async_generate_id()
        webhook_url = \
            self.hass.components.webhook.async_generate_url(webhook_id)

        secret = generate_secret(16)

        if supports_encryption():
            secret_desc = (
                "Go to preferences -> advanced and change encryption key to "
                "`{secret}`.")
        else:
            secret_desc = (
                "Encryption is not supported because libsodium is not "
                "installed.")

        return self.async_create_entry(
            title="OwnTracks",
            data={
                CONF_WEBHOOK_ID: webhook_id,
                CONF_SECRET: secret
            },
            description_placeholders={
                'secret': secret_desc,
                'webhook_url': webhook_url,
                'docs_url':
                'https://www.home-assistant.io/components/owntracks/'
            }
        )
