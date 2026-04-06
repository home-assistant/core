"""Config flow for the GridX integration."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
import json
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .client import async_create_connector
from .const import CONF_OEM, DOMAIN, LOGGER, SUPPORTED_OEMS

UNEXPECTED_AUTH_ERRORS = (RuntimeError, TypeError, ValueError)


def _load_oem_config(oem: str, username: str, password: str) -> dict[str, Any]:
    """Load the OEM config file bundled with gridx-connector and inject credentials."""
    config_path = files("gridx_connector").joinpath("config", f"{oem}.config.json")
    config: dict[str, Any] = json.loads(config_path.read_text())
    config["login"]["username"] = username
    config["login"]["password"] = password
    return config


async def _validate_credentials(
    hass: HomeAssistant,
    oem: str,
    username: str,
    password: str,
) -> None:
    """Attempt authentication and a live data fetch.

    Raises:
        PermissionError: On authentication failure.
        ConnectionError: On network / timeout issues.
        httpx.HTTPError: On HTTP errors from the underlying client.
    """
    config = _load_oem_config(oem, username, password)
    httpx_client = create_async_httpx_client(
        hass,
        auto_cleanup=False,
        base_url="https://api.gridx.de",
    )
    try:
        connector = await async_create_connector(config, httpx_client)
    except BaseException:
        await httpx_client.aclose()
        raise
    try:
        data = await connector.retrieve_live_data()
    finally:
        await connector.close()

    if not data:
        raise ConnectionError("No systems found for this account")


class GridxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GridX."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]
            oem: str = user_input[CONF_OEM]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                await _validate_credentials(self.hass, oem, username, password)
            except PermissionError:
                errors["base"] = "invalid_auth"
            except httpx.HTTPStatusError as err:
                status = err.response.status_code if err.response else None
                errors["base"] = (
                    "invalid_auth" if status in (401, 403) else "cannot_connect"
                )
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            except ConnectionError, TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except UNEXPECTED_AUTH_ERRORS:
                LOGGER.exception("Unexpected error during GridX credential validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_OEM: oem,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_OEM, default="eon-home"): vol.In(SUPPORTED_OEMS),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-authentication confirmation step."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    entry.data[CONF_OEM],
                    entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except PermissionError:
                errors["base"] = "invalid_auth"
            except httpx.HTTPStatusError as err:
                status = err.response.status_code if err.response else None
                errors["base"] = (
                    "invalid_auth" if status in (401, 403) else "cannot_connect"
                )
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            except ConnectionError, TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except UNEXPECTED_AUTH_ERRORS:
                LOGGER.exception("Unexpected error during GridX re-authentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    user_input[CONF_OEM],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except PermissionError:
                errors["base"] = "invalid_auth"
            except httpx.HTTPStatusError as err:
                status = err.response.status_code if err.response else None
                errors["base"] = (
                    "invalid_auth" if status in (401, 403) else "cannot_connect"
                )
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            except ConnectionError, TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except UNEXPECTED_AUTH_ERRORS:
                LOGGER.exception("Unexpected error during GridX reconfiguration")
                errors["base"] = "unknown"
            else:
                new_username = user_input[CONF_USERNAME]
                if new_username.lower() != entry.unique_id:
                    await self.async_set_unique_id(new_username.lower())
                    self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: new_username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_OEM: user_input[CONF_OEM],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                ): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_OEM, default=entry.data.get(CONF_OEM, "eon-home")
                ): vol.In(SUPPORTED_OEMS),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )
