"""Config flow to configure Renault component."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (  # pylint: disable=unused-import
    AVAILABLE_LOCALES,
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DOMAIN,
)
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
        if user_input:
            self.renault_config.update(user_input)
            self.pyzeproxy = PyzeProxy(self.hass, self.renault_config)
            if not await self.pyzeproxy.attempt_login():
                return self._show_user_form({"base": "invalid_credentials"})

            self.renault_config = user_input
            return await self.async_step_kamereon()
        return self._show_user_form()

    def _show_user_form(self, errors=None):
        """Show the credentials form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_LOCALE): vol.In(AVAILABLE_LOCALES),
                }
            ),
            errors=errors if errors else {},
        )

    async def async_step_kamereon(self, user_input=None):
        """Select Kamereon account."""
        if user_input:
            self.renault_config.update(user_input)
            return self.async_create_entry(
                title=user_input[CONF_KAMEREON_ACCOUNT_ID], data=self.renault_config
            )

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
