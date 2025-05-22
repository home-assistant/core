"""Config flow for the Paperless-ngx integration."""

from __future__ import annotations

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
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
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
                    CONF_URL: user_input[CONF_URL],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            client = Paperless(
                user_input[CONF_URL],
                user_input[CONF_API_KEY],
                session=async_get_clientsession(self.hass),
            )

            try:
                await client.initialize()
                await client.statistics()
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
            else:
                return self.async_create_entry(
                    title=user_input[CONF_URL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
