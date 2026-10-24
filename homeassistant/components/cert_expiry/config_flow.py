"""Config flow for the Cert Expiry platform."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import CONF_CA_CERTIFICATES, DEFAULT_PORT, DOMAIN
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    InvalidCACertificate,
    ResolveFailed,
    ValidationFailure,
)
from .helper import (
    async_get_ssl_context,
    get_cert_expiry_timestamp,
    normalize_ca_certificates,
)


class CertexpiryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._ca_certificates = ""

    async def _test_connection(
        self,
        user_input: Mapping[str, Any],
    ) -> bool:
        """Test connection to the server and try to get the certificate."""
        try:
            self._ca_certificates = await self.hass.async_add_executor_job(
                normalize_ca_certificates, user_input[CONF_CA_CERTIFICATES]
            )
            ssl_context = await async_get_ssl_context(
                self.hass,
                verify_ssl=user_input[CONF_VERIFY_SSL],
                ca_certificates=self._ca_certificates,
            )
        except InvalidCACertificate:
            self._errors[CONF_CA_CERTIFICATES] = "invalid_ca_certificates"
            return False

        try:
            await get_cert_expiry_timestamp(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
                verify_ssl=user_input[CONF_VERIFY_SSL],
                ssl_context=ssl_context,
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

    @override
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
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_CA_CERTIFICATES: self._ca_certificates,
                    },
                )
        else:
            user_input = {}
            user_input[CONF_HOST] = ""
            user_input[CONF_PORT] = DEFAULT_PORT

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    probatio.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    probatio.Required(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
                    ): bool,
                    probatio.Optional(
                        CONF_CA_CERTIFICATES,
                        default=user_input.get(CONF_CA_CERTIFICATES, ""),
                    ): TextSelector(TextSelectorConfig(multiline=True)),
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
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_CA_CERTIFICATES: self._ca_certificates,
                    },
                    unique_id=f"{host}:{port}",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): str,
                        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
                        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
                        probatio.Optional(
                            CONF_CA_CERTIFICATES, default=""
                        ): TextSelector(TextSelectorConfig(multiline=True)),
                    }
                ),
                user_input or reconfigure_entry.data,
            ),
            errors=self._errors,
        )
