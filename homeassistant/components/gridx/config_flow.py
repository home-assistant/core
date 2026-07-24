"""Config flow for the GridX integration."""

from typing import Any, override

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .client import async_create_connector, load_oem_config
from .const import API_BASE_URL, DOMAIN, LOGGER

UNEXPECTED_AUTH_ERRORS = (RuntimeError, TypeError, ValueError)


class _NoSystemsFoundError(Exception):
    """Raised when authentication succeeds but no GridX systems are found."""


async def _validate_credentials(
    hass: HomeAssistant,
    username: str,
    password: str,
) -> None:
    """Attempt authentication and a live data fetch.

    Raises:
        PermissionError: On authentication failure.
        ConnectionError: On network / timeout issues.
        httpx.HTTPError: On HTTP errors from the underlying client.
    """
    config = await hass.async_add_executor_job(load_oem_config, username, password)
    httpx_client = create_async_httpx_client(
        hass,
        auto_cleanup=False,
        base_url=API_BASE_URL,
    )
    try:
        connector = await async_create_connector(config, httpx_client)
    except Exception:
        await httpx_client.aclose()
        raise
    try:
        data = await connector.retrieve_live_data()
    finally:
        await connector.close()

    if not data:
        raise _NoSystemsFoundError


class GridxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GridX."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                await _validate_credentials(self.hass, username, password)
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
            except _NoSystemsFoundError:
                errors["base"] = "no_systems"
            except UNEXPECTED_AUTH_ERRORS:
                LOGGER.exception("Unexpected error during GridX credential validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
