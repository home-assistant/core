"""Config flow for the Cert Expiry platform."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from ...core import callback
from .const import CONF_CA_CERT, DEFAULT_PORT, DOMAIN  # pylint: disable=unused-import
from .errors import (
    ConnectionRefused,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)
from .helper import get_cert_expiry_timestamp

_LOGGER = logging.getLogger(__name__)


class CertexpiryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors = {}

    async def _test_connection(self, user_input=None):
        """Test connection to the server and try to get the certificate."""
        try:
            await get_cert_expiry_timestamp(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
                user_input.get(CONF_CA_CERT, None),
            )
            return True
        except ResolveFailed:
            self._errors[CONF_HOST] = "resolve_failed"
        except ConnectionTimeout:
            self._errors[CONF_HOST] = "connection_timeout"
        except ConnectionRefused:
            self._errors[CONF_HOST] = "connection_refused"
        except ValidationFailure:
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            ca_cert = user_input.get(CONF_CA_CERT, "")
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            if await self._test_connection(user_input):
                title_port = f":{port}" if port != DEFAULT_PORT else ""
                title = f"{host}{title_port}"
                data = {CONF_HOST: host, CONF_PORT: port}
                if ca_cert != "":
                    data[CONF_CA_CERT] = ca_cert
                return self.async_create_entry(title=title, data=data,)
            if (  # pylint: disable=no-member
                self.context["source"] == config_entries.SOURCE_IMPORT
            ):
                _LOGGER.error("Config import failed for %s", user_input[CONF_HOST])
                return self.async_abort(reason="import_failed")
        else:
            user_input = {CONF_HOST: "", CONF_PORT: DEFAULT_PORT, CONF_CA_CERT: ""}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(CONF_CA_CERT, default=user_input[CONF_CA_CERT]): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry.

        Only host was required in the yaml file all other fields are optional
        """
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Set the options flow handler for cert_expiry."""

        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """The option flow handler for cert_expiry."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage cert_expiry options."""
        if user_input is not None:
            ca_cert = user_input.get(CONF_CA_CERT, "")
            data = self.config_entry.options.copy()
            if ca_cert != "":
                data[CONF_CA_CERT] = ca_cert
            else:
                data.pop(CONF_CA_CERT, None)
            return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CA_CERT,
                        default=self.config_entry.options.get(CONF_CA_CERT, ""),
                    ): str
                }
            ),
        )
