"""Config flow for the Paperless-ngx integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pypaperless import Paperless
from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import PaperlessCoordinator

type PaperlessConfigEntry = ConfigEntry[PaperlessCoordinator]


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class PaperlessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paperless-ngx."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            aiohttp_session = async_get_clientsession(self.hass)
            client = Paperless(
                user_input[CONF_HOST],
                user_input[CONF_API_KEY],
                session=aiohttp_session,
            )

            try:
                await client.initialize()
                await client.statistics()
            except PaperlessConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except PaperlessInvalidTokenError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except PaperlessInactiveOrDeletedError:
                errors[CONF_API_KEY] = "user_inactive_or_deleted"
            except PaperlessForbiddenError:
                errors[CONF_API_KEY] = "forbidden"
            except InitializationError:
                errors[CONF_HOST] = "cannot_connect"
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure flow for Paperless-ngx integration."""
        return await self.async_step_reauth_confirm(user_input)

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
                    user_input[CONF_API_KEY],
                    session=aiohttp_session,
                )
                await client.initialize()
                await client.statistics()

            except PaperlessConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except PaperlessInvalidTokenError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except PaperlessInactiveOrDeletedError:
                errors[CONF_API_KEY] = "user_inactive_or_deleted"
            except PaperlessForbiddenError:
                errors[CONF_API_KEY] = "forbidden"
            except InitializationError:
                errors[CONF_HOST] = "cannot_connect"
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
                },
            ),
            errors=errors,
        )
