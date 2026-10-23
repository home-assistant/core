"""Configure a The Things Stack connection."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
import logging
from typing import Any, override

from lorawan_connection import ConnectionUnavailable
from lorawan_connection.backend.tts import (
    TTN_REGIONS,
    AuthenticationError,
    TTSConnection,
)
import probatio
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_REGION
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_APPLICATION_IDS,
    CONF_ENDPOINT,
    CONF_IDENTITY_SERVER,
    DOMAIN,
    TTN_IDENTITY_SERVER,
)

_LOGGER = logging.getLogger(__name__)


class TheThingsNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Connect selected applications to LoRaWAN."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize pending input."""
        self._input: dict[str, Any] = {}
        self._custom_server = False
        self._applications: dict[str, str] = {}

    @asynccontextmanager
    async def _async_connection(
        self, errors: dict[str, str]
    ) -> AsyncIterator[TTSConnection]:
        """Translate request errors and close the temporary connection."""
        connection = TTSConnection(
            self._input[CONF_ENDPOINT],
            self._input[CONF_API_KEY],
            identity_server=self._input[CONF_IDENTITY_SERVER],
            application_ids=self._input.get(CONF_APPLICATION_IDS, []),
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
        """Select a The Things Network region or a custom server."""
        if user_input is not None:
            region = user_input[CONF_REGION]
            self._custom_server = region == "custom"
            if not self._custom_server:
                self._input = {
                    CONF_ENDPOINT: f"https://{region}.cloud.thethings.network:8884",
                    CONF_IDENTITY_SERVER: TTN_IDENTITY_SERVER,
                }
            return await self.async_step_connection()
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_REGION, default="eu1"): SelectSelector(
                        SelectSelectorConfig(
                            options=[*TTN_REGIONS, "custom"],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_REGION,
                        )
                    )
                }
            ),
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the API key and fetch available applications."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._custom_server:
                self._input = dict(user_input)
            else:
                self._input.update(user_input)
            self._input.pop(CONF_APPLICATION_IDS, None)
            try:
                for key in (CONF_ENDPOINT, CONF_IDENTITY_SERVER):
                    if endpoint := self._input.get(key, "").strip():
                        self._input[key] = str(URL(endpoint).with_path(""))
                self._input[CONF_IDENTITY_SERVER] = (
                    self._input.get(CONF_IDENTITY_SERVER, "").strip()
                    or self._input[CONF_ENDPOINT]
                )
                async with self._async_connection(errors) as connection:
                    self._applications = await connection.applications()
            except ValueError:
                errors["base"] = "invalid_endpoint"
            if not errors:
                return await self.async_step_applications()
        return self._show_connection_form(errors)

    def _show_connection_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Ask for credentials and custom server addresses."""
        fields: dict[probatio.Marker, Any] = {}
        if self._custom_server:
            fields.update(
                {
                    probatio.Required(CONF_ENDPOINT): str,
                    probatio.Optional(CONF_IDENTITY_SERVER): str,
                }
            )
        fields[probatio.Required(probatio.Secret(CONF_API_KEY))] = str
        return self.async_show_form(
            step_id="connection",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(fields),
                self._input,
            ),
            errors=errors,
        )

    async def async_step_applications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select applications and validate device and traffic access."""
        if not self._applications:
            return self.async_abort(reason="no_applications")
        errors: dict[str, str] = {}
        if user_input is not None:
            applications = sorted(set(user_input[CONF_APPLICATION_IDS]))
            if not applications:
                errors[CONF_APPLICATION_IDS] = "select_application"
            else:
                self._input[CONF_APPLICATION_IDS] = applications
                async with self._async_connection(errors) as connection:
                    await connection.async_connect()
                if not errors:
                    identity_server = self._input[CONF_IDENTITY_SERVER]
                    await self.async_set_unique_id(
                        f"{identity_server}:{','.join(applications)}"
                    )
                    self._abort_if_unique_id_configured()
                    for entry in self._async_current_entries(include_ignore=False):
                        if str(
                            URL(entry.data[CONF_IDENTITY_SERVER])
                        ) == identity_server and set(
                            entry.data[CONF_APPLICATION_IDS]
                        ).intersection(applications):
                            raise AbortFlow("already_configured")
                    return self.async_create_entry(
                        title=", ".join(applications), data=self._input
                    )
        if errors.get("base") == "invalid_auth":
            return self._show_connection_form(errors)
        return self.async_show_form(
            step_id="applications",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_APPLICATION_IDS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=name)
                                for key, name in self._applications.items()
                            ],
                            multiple=True,
                        )
                    )
                }
            ),
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
