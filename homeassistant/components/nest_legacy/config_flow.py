"""Adds config flow for Nest."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_ACCOUNT_TYPE,
    CONF_COOKIES,
    CONF_ENABLE_PROTOBUF_CAMERA,
    CONF_ENABLE_PROTOBUF_LOCK,
    CONF_ENABLE_PROTOBUF_PROTECT,
    CONF_ENABLE_PROTOBUF_STRUCTURE,
    CONF_ENABLE_PROTOBUF_THERMOSTAT,
    CONF_EVENT_POLL_INTERVAL,
    CONF_FIELD_TEST,
    CONF_ISSUE_TOKEN,
    DEFAULT_EVENT_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import NestConfigEntry
from .pynest.client import NestClient
from .pynest.exceptions import BadCredentialsException


class NestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Nest."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._options: dict[str, Any] = {}

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user credentials."""
        account_type = self._options[CONF_ACCOUNT_TYPE]
        field_test = self._options.get(CONF_FIELD_TEST, False)

        client = NestClient(async_create_clientsession(self.hass), field_test)

        nest_session = None
        if account_type == "google":
            issue_token = user_input[CONF_ISSUE_TOKEN]
            cookies = user_input[CONF_COOKIES]
            nest_session = await client.async_authenticate_with_google_credentials(
                issue_token, cookies
            )
        elif account_type == "nest":
            access_token = user_input[CONF_ACCESS_TOKEN]
            nest_session = await client.async_authenticate_with_nest_token(access_token)
        else:
            raise ValueError("Invalid account type")

        await self.async_set_unique_id(nest_session.user)
        return {"title": f"Nest{' FT' if field_test else ''} ({nest_session.email})"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._options = user_input
            account_type = user_input[CONF_ACCOUNT_TYPE]
            if account_type == "google":
                return await self.async_step_google_account()
            if account_type == "nest":
                return await self.async_step_nest_account()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_TYPE, default="google"): vol.In(
                        {"google": "Google Account", "nest": "Nest Account"}
                    ),
                    vol.Optional(CONF_FIELD_TEST, default=False): bool,
                }
            ),
        )

    async def _show_form_and_handle_errors(
        self,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Show form, validate input, and handle exceptions."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                info = await self._validate_input(user_input)
            except TimeoutError, ClientError:
                errors["base"] = "cannot_connect"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unknown error during validation")
                errors["base"] = "unknown"
            else:
                data = {**self._options, **user_input}
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=data
                    )
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data=data
                    )

                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_google_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Google Account authentication."""
        schema = vol.Schema(
            {vol.Required(CONF_ISSUE_TOKEN): str, vol.Required(CONF_COOKIES): str}
        )
        return await self._show_form_and_handle_errors(
            "google_account", schema, user_input
        )

    async def async_step_nest_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Nest Account authentication."""
        schema = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
        return await self._show_form_and_handle_errors(
            "nest_account", schema, user_input
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        reauth_entry = self._get_reauth_entry()
        self._options = dict(reauth_entry.data)
        return await self.async_step_user(self._options)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        self._options = dict(reconfigure_entry.data)
        return await self.async_step_user(self._options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: NestConfigEntry) -> OptionsFlowWithReload:
        """Create the options flow."""
        return NestOptionsFlowHandler()


class NestOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_EVENT_POLL_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_EVENT_POLL_INTERVAL, DEFAULT_EVENT_POLL_INTERVAL
                ),
            ): int,
            vol.Optional(
                CONF_ENABLE_PROTOBUF_LOCK,
                default=self.config_entry.options.get(CONF_ENABLE_PROTOBUF_LOCK, True),
            ): bool,
            vol.Optional(
                CONF_ENABLE_PROTOBUF_THERMOSTAT,
                default=self.config_entry.options.get(
                    CONF_ENABLE_PROTOBUF_THERMOSTAT, True
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_PROTOBUF_STRUCTURE,
                default=self.config_entry.options.get(
                    CONF_ENABLE_PROTOBUF_STRUCTURE, False
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_PROTOBUF_PROTECT,
                default=self.config_entry.options.get(
                    CONF_ENABLE_PROTOBUF_PROTECT, False
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_PROTOBUF_CAMERA,
                default=self.config_entry.options.get(
                    CONF_ENABLE_PROTOBUF_CAMERA,
                    self.config_entry.data.get(CONF_ACCOUNT_TYPE) == "google",
                ),
            ): bool,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(options))
