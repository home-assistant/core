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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class PaperlessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paperless-ngx."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_URL: user_input[CONF_URL],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )

            errors = await self._validate_input(user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_URL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure flow for Paperless-ngx integration."""

        entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_URL: user_input[CONF_URL],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )

            errors = await self._validate_input(user_input)

            if not errors:
                return self.async_update_reload_and_abort(entry, data=user_input)

        if user_input is not None:
            suggested_values = user_input
        else:
            suggested_values = {
                CONF_URL: entry.data[CONF_URL],
                CONF_VERIFY_SSL: entry.data.get(CONF_VERIFY_SSL, True),
            }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values=suggested_values,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth flow for Paperless-ngx integration."""

        entry = self._get_reauth_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            updated_data = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}

            errors = await self._validate_input(updated_data)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data=updated_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}

        client = Paperless(
            user_input[CONF_URL],
            user_input[CONF_API_KEY],
            session=async_get_clientsession(
                self.hass, user_input.get(CONF_VERIFY_SSL, True)
            ),
        )

        try:
            await client.initialize()
            await client.statistics()  # test permissions on api
        except PaperlessConnectionError:
            errors[CONF_URL] = "cannot_connect"
        except PaperlessInvalidTokenError:
            errors[CONF_API_KEY] = "invalid_api_key"
        except PaperlessInactiveOrDeletedError:
            errors[CONF_API_KEY] = "user_inactive_or_deleted"
        except PaperlessForbiddenError:
            errors[CONF_API_KEY] = "forbidden"
        except InitializationError:
            errors[CONF_URL] = "cannot_connect"
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected exception: %s", err)
            errors["base"] = "unknown"

        return errors
