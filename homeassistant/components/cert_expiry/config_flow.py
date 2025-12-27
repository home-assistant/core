"""Config flow for the Cert Expiry platform."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VALIDATE_CERT_FULL

from .const import DEFAULT_PORT, DEFAULT_VALIDATE_CERT_FULL, DOMAIN
from .errors import (
    ConnectionRefused,
    ConnectionReset,
    ConnectionTimeout,
    ResolveFailed,
    ValidationFailure,
)
from .helper import get_cert

_LOGGER = logging.getLogger(__name__)


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
            await get_cert(
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
        """Step when user initializes an integration."""
        self._errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            validate_cert_full = user_input.get(
                CONF_VALIDATE_CERT_FULL, DEFAULT_VALIDATE_CERT_FULL
            )
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
                        CONF_VALIDATE_CERT_FULL: validate_cert_full,
                    },
                )
            if self.source == SOURCE_IMPORT:
                _LOGGER.error("Config import failed for %s", user_input[CONF_HOST])
                return self.async_abort(reason="import_failed")
        else:
            user_input = {
                CONF_HOST: "",
                CONF_PORT: DEFAULT_PORT,
                CONF_VALIDATE_CERT_FULL: DEFAULT_VALIDATE_CERT_FULL,
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_VALIDATE_CERT_FULL,
                        default=user_input.get(
                            CONF_VALIDATE_CERT_FULL, DEFAULT_VALIDATE_CERT_FULL
                        ),
                    ): bool,
                }
            ),
            errors=self._errors,
        )
