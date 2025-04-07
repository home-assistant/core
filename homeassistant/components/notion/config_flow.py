"""Config flow to configure the Notion integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from aionotion.errors import InvalidCredentialsError, NotionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN, CONF_USER_UUID, DOMAIN, LOGGER
from .util import async_get_client_with_credentials

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


@dataclass(frozen=True, kw_only=True)
class CredentialsValidationResult:
    """Define a validation result."""

    user_uuid: str | None = None
    refresh_token: str | None = None
    errors: dict[str, Any] = field(default_factory=dict)


async def async_validate_credentials(
    hass: HomeAssistant, username: str, password: str
) -> CredentialsValidationResult:
    """Validate a Notion username and password."""
    errors = {}

    try:
        client = await async_get_client_with_credentials(hass, username, password)
    except InvalidCredentialsError:
        errors["base"] = "invalid_auth"
    except NotionError as err:
        LOGGER.error("Unknown Notion error while validation credentials: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # noqa: BLE001
        LOGGER.exception("Unknown error while validation credentials: %s", err)
        errors["base"] = "unknown"

    if errors:
        return CredentialsValidationResult(errors=errors)

    return CredentialsValidationResult(
        user_uuid=client.user_uuid, refresh_token=client.refresh_token
    )


class NotionFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Notion config flow."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""

        reauth_entry = self._get_reauth_entry()
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                description_placeholders={
                    CONF_USERNAME: reauth_entry.data[CONF_USERNAME]
                },
            )

        credentials_validation_result = await async_validate_credentials(
            self.hass, reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if credentials_validation_result.errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                errors=credentials_validation_result.errors,
                description_placeholders={
                    CONF_USERNAME: reauth_entry.data[CONF_USERNAME]
                },
            )

        return self.async_update_reload_and_abort(
            reauth_entry,
            data_updates={
                CONF_REFRESH_TOKEN: credentials_validation_result.refresh_token
            },
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=AUTH_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        credentials_validation_result = await async_validate_credentials(
            self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if credentials_validation_result.errors:
            return self.async_show_form(
                step_id="user",
                data_schema=AUTH_SCHEMA,
                errors=credentials_validation_result.errors,
            )

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_USER_UUID: credentials_validation_result.user_uuid,
                CONF_REFRESH_TOKEN: credentials_validation_result.refresh_token,
            },
        )
