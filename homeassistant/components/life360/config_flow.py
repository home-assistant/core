"""Config flow to configure Life360 integration."""
from collections import OrderedDict
import logging

from life360 import Life360Error, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_AUTHORIZATION, DOMAIN
from .helpers import get_api

_LOGGER = logging.getLogger(__name__)

DOCS_URL = "https://www.home-assistant.io/integrations/life360"


class Life360ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Life360 integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._api = get_api()
        self._username = vol.UNDEFINED
        self._password = vol.UNDEFINED

    @property
    def configured_usernames(self):
        """Return tuple of configured usernames."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return (entry.data[CONF_USERNAME] for entry in entries)
        return ()

    async def async_step_user(self, user_input=None):
        """Handle a user initiated config flow."""
        errors = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            try:
                # pylint: disable=no-value-for-parameter
                vol.Email()(self._username)
                authorization = await self.hass.async_add_executor_job(
                    self._api.get_authorization, self._username, self._password
                )
            except vol.Invalid:
                errors[CONF_USERNAME] = "invalid_username"
            except LoginError:
                errors["base"] = "invalid_auth"
            except Life360Error as error:
                _LOGGER.error(
                    "Unexpected error communicating with Life360 server: %s", error
                )
                errors["base"] = "unknown"
            else:
                if self._username in self.configured_usernames:
                    errors["base"] = "already_configured"
                else:
                    return self.async_create_entry(
                        title=self._username,
                        data={
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                            CONF_AUTHORIZATION: authorization,
                        },
                        description_placeholders={"docs_url": DOCS_URL},
                    )

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME, default=self._username)] = str
        data_schema[vol.Required(CONF_PASSWORD, default=self._password)] = str

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
            description_placeholders={"docs_url": DOCS_URL},
        )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        try:
            authorization = await self.hass.async_add_executor_job(
                self._api.get_authorization, username, password
            )
        except LoginError:
            _LOGGER.error("Invalid credentials for %s", username)
            return self.async_abort(reason="invalid_auth")
        except Life360Error as error:
            _LOGGER.error(
                "Unexpected error communicating with Life360 server: %s", error
            )
            return self.async_abort(reason="unknown")
        return self.async_create_entry(
            title=f"{username} (from configuration)",
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_AUTHORIZATION: authorization,
            },
        )
