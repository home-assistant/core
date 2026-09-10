"""Config flow for the Cert Expiry platform."""

from collections.abc import Mapping
import ssl
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CA_DATA, CONF_HOST, CONF_IGNORE_HOSTNAME, CONF_PORT
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DOMAIN
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)
from .helper import get_cert_expiry_timestamp


def _iter_pem_certs(pem_data: str) -> list[str]:
    """Split the string into individual certificate blocks."""

    pem_data = pem_data.strip()
    if not pem_data or pem_data == "":
        return []
    begin_marker = "-----BEGIN CERTIFICATE-----"
    end_marker = "-----END CERTIFICATE-----"
    certs: list[str] = []
    pos = 0
    while True:
        start = pem_data.find(begin_marker, pos)
        if start == -1:
            break
        end = pem_data.find(end_marker, start)
        if end == -1:
            # BEGIN without matching END -> malformed PEM
            raise ValueError("Missing END CERTIFICATE marker")
        end += len(end_marker)
        certs.append(pem_data[start:end])
        pos = end
    return certs


class CertexpiryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    async def _test_connection(
        self,
        user_input: Mapping[str, Any],
    ) -> bool:
        """Test connection to the server and try to get the certificate."""
        ca_data = user_input.get(CONF_CA_DATA) or None
        if ca_data and not ca_data.strip():
            ca_data = None
        if ca_data:
            try:
                pem_blocks = _iter_pem_certs(ca_data)
                if not pem_blocks:
                    self._errors[CONF_CA_DATA] = "invalid_pem"
                    return False
                for pem_block in pem_blocks:
                    ssl.PEM_cert_to_DER_cert(pem_block)
            except ValueError:
                self._errors[CONF_CA_DATA] = "invalid_pem"
                return False

        try:
            await get_cert_expiry_timestamp(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
                user_input.get(CONF_IGNORE_HOSTNAME, False),
                ca_data,
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
            self._errors[CONF_HOST] = "validation_failed"
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
            ignore_hostname = user_input.get(CONF_IGNORE_HOSTNAME, False)
            ca_data = user_input.get(CONF_CA_DATA, None)
            if ca_data and not ca_data.strip():
                ca_data = None
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
                        CONF_IGNORE_HOSTNAME: ignore_hostname,
                        CONF_CA_DATA: ca_data,
                    },
                )
        else:
            user_input = {}
            user_input[CONF_HOST] = ""
            user_input[CONF_PORT] = DEFAULT_PORT
            user_input[CONF_IGNORE_HOSTNAME] = False
            user_input[CONF_CA_DATA] = None
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_IGNORE_HOSTNAME,
                        default=user_input.get(CONF_IGNORE_HOSTNAME, False),
                    ): bool,
                    vol.Optional(CONF_CA_DATA): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
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
