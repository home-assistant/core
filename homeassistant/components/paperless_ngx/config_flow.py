"""Config flow for the Paperless-ngx integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectionError, ClientConnectorError
from pypaperless import Paperless
from pypaperless.api import (
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.exceptions import InitializationError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_SCAN_INTERVAL, default=180): vol.All(
            int,
            vol.Range(min=10, max=3600),
        ),
    }
)


class PaperlessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paperless-ngx."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                }
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                aiohttp_session = async_get_clientsession(self.hass)
                client = Paperless(
                    user_input[CONF_HOST],
                    user_input[CONF_ACCESS_TOKEN],
                    session=aiohttp_session,
                )
                await client.initialize()
                await client.statistics()
            except (InitializationError, ClientConnectorError, ClientConnectionError):
                errors[CONF_HOST] = "cannot_connect"
            except PaperlessInvalidTokenError:
                errors[CONF_ACCESS_TOKEN] = "invalid_auth"
            except PaperlessInactiveOrDeletedError:
                errors[CONF_ACCESS_TOKEN] = "user_inactive_or_deleted"
            except PaperlessForbiddenError:
                errors["base"] = "forbidden"
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Paperless-ngx", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        reauth_entry = (
            self._get_reauth_entry()
            if self.source == SOURCE_REAUTH
            else self._get_reconfigure_entry()
        )
        if user_input is not None:
            try:
                aiohttp_session = async_get_clientsession(self.hass)
                client = Paperless(
                    user_input[CONF_HOST],
                    user_input[CONF_ACCESS_TOKEN],
                    session=aiohttp_session,
                )
                await client.initialize()
                await client.statistics()

            except (InitializationError, ClientConnectorError, ClientConnectionError):
                errors[CONF_HOST] = "cannot_connect"
            except PaperlessInvalidTokenError:
                errors[CONF_ACCESS_TOKEN] = "invalid_auth"
            except PaperlessInactiveOrDeletedError:
                errors[CONF_ACCESS_TOKEN] = "user_inactive_or_deleted"
            except PaperlessForbiddenError:
                errors["base"] = "forbidden"
            except Exception as err:  # noqa: BLE001
                LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            step_id="reauth_confirm" if self.source == SOURCE_REAUTH else "reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values={
                    CONF_HOST: user_input[CONF_HOST]
                    if user_input is not None
                    else reauth_entry.data[CONF_HOST],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]
                    if user_input is not None
                    else reauth_entry.data[CONF_SCAN_INTERVAL],
                },
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure flow for ista EcoTrend integration."""
        return await self.async_step_reauth_confirm(user_input)
