"""Config flow to configure Renault component."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_KAMEREON_ACCOUNT_ID, DOMAIN  # pylint: disable=unused-import
from .pyzeproxy import PyzeProxy


class RenaultFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Renault config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Renault config flow."""
        self.renault_config = {}
        self.pyzeproxy = None

    async def async_step_user(self, user_input=None):
        """Handle a Renault config flow start.

        Ask the user for credentials.
        """
        if not user_input:
            return self._show_user_form()

        self.pyzeproxy = PyzeProxy(self.hass)
        if not await self.pyzeproxy.attempt_login(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        ):
            return self._show_user_form({"base": "invalid_credentials"})

        self.renault_config = user_input
        return await self.async_step_kamereon()

    def _show_user_form(self, errors=None):
        """Show the credentials form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors if errors else {},
        )

    async def async_step_kamereon(self, user_input=None):
        """Select Kamereon account."""
        if user_input:
            account_id = user_input[CONF_KAMEREON_ACCOUNT_ID]
            self.renault_config[CONF_KAMEREON_ACCOUNT_ID] = account_id
            return self.async_create_entry(title=account_id, data=self.renault_config)

        accounts = await self.pyzeproxy.get_account_ids()
        if len(accounts) == 0:
            return self.async_abort(reason="kamereon_no_account")
        if len(accounts) == 1:
            self.renault_config[CONF_KAMEREON_ACCOUNT_ID] = accounts[0]
            return self.async_create_entry(
                title=self.renault_config[CONF_KAMEREON_ACCOUNT_ID],
                data=self.renault_config,
            )

        return self.async_show_form(
            step_id="kamereon",
            data_schema=vol.Schema(
                {vol.Required(CONF_KAMEREON_ACCOUNT_ID): vol.In(accounts)}
            ),
        )
