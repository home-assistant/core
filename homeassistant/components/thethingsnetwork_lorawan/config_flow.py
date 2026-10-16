"""Configure a The Things Stack connection."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
import logging
from typing import Any, override
from urllib.parse import urlsplit

from lorawan_connection import ConnectionUnavailable
from lorawan_connection.backend.tts import AuthenticationError, TTSConnection
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import (
    CONF_APPLICATION_IDS,
    CONF_ENDPOINT,
    CONF_IDENTITY_SERVER,
    DEFAULT_ENDPOINT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TheThingsNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Connect selected applications to LoRaWAN."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize pending input."""
        self._input: dict[str, Any] = {}

    @asynccontextmanager
    async def _async_connection(
        self, errors: dict[str, str]
    ) -> AsyncIterator[TTSConnection]:
        """Translate request errors and close the temporary connection."""
        connection = TTSConnection(
            self._input[CONF_ENDPOINT],
            self._input[CONF_API_KEY],
            identity_server=self._input[CONF_IDENTITY_SERVER],
            application_ids=self._input[CONF_APPLICATION_IDS],
            network_id="validation",
        )
        try:
            yield connection
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except ConnectionUnavailable:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error communicating with The Things Stack")
            errors["base"] = "unknown"
        finally:
            await connection.close()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate access to the selected applications and both servers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._input = dict(user_input)
            self._input[CONF_APPLICATION_IDS] = sorted(
                {app.strip() for app in user_input[CONF_APPLICATION_IDS] if app.strip()}
            )
            if not self._input[CONF_APPLICATION_IDS]:
                errors[CONF_APPLICATION_IDS] = "select_application"
            else:
                try:
                    for key in (CONF_ENDPOINT, CONF_IDENTITY_SERVER):
                        if endpoint := self._input.get(key, "").strip():
                            self._input[key] = (
                                urlsplit(endpoint)
                                ._replace(path="", query="", fragment="")
                                .geturl()
                            )
                    self._input[CONF_IDENTITY_SERVER] = (
                        self._input.get(CONF_IDENTITY_SERVER, "").strip()
                        or self._input[CONF_ENDPOINT]
                    )
                    async with self._async_connection(errors) as connection:
                        await connection.async_connect()
                except ValueError:
                    errors["base"] = "invalid_endpoint"
                if not errors:
                    identity_server = self._input[CONF_IDENTITY_SERVER]
                    applications = self._input[CONF_APPLICATION_IDS]
                    await self.async_set_unique_id(
                        f"{identity_server}:{','.join(applications)}"
                    )
                    self._abort_if_unique_id_configured()
                    for entry in self._async_current_entries(include_ignore=False):
                        if entry.data[CONF_IDENTITY_SERVER] == identity_server and set(
                            entry.data[CONF_APPLICATION_IDS]
                        ).intersection(applications):
                            raise AbortFlow("already_configured")
                    return self.async_create_entry(
                        title=", ".join(applications), data=self._input
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): str,
                        probatio.Optional(CONF_IDENTITY_SERVER): str,
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_APPLICATION_IDS): TextSelector(
                            TextSelectorConfig(multiple=True)
                        ),
                    }
                ),
                self._input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Replace rejected credentials without changing network identity."""
        self._input = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the replacement key against the existing applications."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._input.update(user_input)
            async with self._async_connection(errors) as connection:
                await connection.async_connect()
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
        )
