"""Config flow for the Cert Expiry platform."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)
from .helper import get_cert_expiry_timestamp


class CertexpiryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    async def _test_connection(
        self,
        user_input: Mapping[str, Any],
    ) -> bool:
        """Test connection to the server and try to get the certificate."""
        try:
            await get_cert_expiry_timestamp(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
            )
        except ResolveFailed:
            self._errors[CONF_HOST] = "resolve_failed"
        except ConnectionTimeout:
            self._errors[CONF_HOST] = "connection_timeout"
        except ConnectionRefused:
            self._errors[CONF_HOST] = "connection_refused"
        except ConnectionReset:
            self._errors[CONF_HOST] = "connection_reset"
        except ValidationFailure:
            return True
        else:
            return True
        return False

    async def async_step_user(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            if await self._test_connection(user_input):
                title_port = f":{port}" if port != DEFAULT_PORT else ""
                title = f"{host}{title_port}"
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port},
                )
        else:
            user_input = {}
            user_input[CONF_HOST] = ""
            user_input[CONF_PORT] = DEFAULT_PORT

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=self._errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        self._errors = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            if (
                host != reconfigure_entry.data[CONF_HOST]
                or port != reconfigure_entry.data[CONF_PORT]
            ):
                self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            if await self._test_connection(user_input):
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port},
                    unique_id=f"{host}:{port}",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    }
                ),
                user_input or reconfigure_entry.data,
            ),
            errors=self._errors,
        )
