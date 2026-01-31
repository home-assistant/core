"""Config flow for the LoJack integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lojack_api import ApiError, AuthenticationError, LoJackClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, LOGGER

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class LoJackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LoJack."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None

    async def _async_validate_credentials(
        self, username: str, password: str
    ) -> dict[str, str]:
        """Validate credentials and return errors dict."""
        errors: dict[str, str] = {}

        try:
            client = await LoJackClient.create(username, password)
            # Test that we can list devices
            await client.list_devices()
            await client.close()
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except ApiError as err:
            LOGGER.error("LoJack API error: %s", err)
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error during LoJack authentication")
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        # Check for duplicate config entries
        await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        errors = await self._async_validate_credentials(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=f"LoJack ({user_input[CONF_USERNAME]})",
            data=user_input,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_REAUTH_SCHEMA
            )

        # _username is set in async_step_reauth before calling this method
        if self._username is None:
            return self.async_abort(reason="unknown")

        errors = await self._async_validate_credentials(
            self._username, user_input[CONF_PASSWORD]
        )

        if errors:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_REAUTH_SCHEMA, errors=errors
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
        )
