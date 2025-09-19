"""Config flow for Matrix integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from nio import AsyncClient, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_HOMESERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOMESERVER): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = AsyncClient(
        homeserver=data[CONF_HOMESERVER],
        user=data[CONF_USERNAME],
        ssl=data[CONF_VERIFY_SSL],
    )

    login_response = await client.login(data[CONF_PASSWORD])
    if isinstance(login_response, LoginError):
        await client.close()
        raise ConnectionError

    # Get user info to validate connection
    whoami_response = await client.whoami()
    if hasattr(whoami_response, "user_id"):
        user_id = whoami_response.user_id
    else:
        user_id = data[CONF_USERNAME]

    await client.close()
    return {"title": user_id, "user_id": user_id}


class MatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["user_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        try:
            info = await validate_input(self.hass, import_data)
        except Exception:
            _LOGGER.exception("Failed to validate imported YAML config")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(info["user_id"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{info['title']} (from YAML)",
            data=import_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self.reauth_entry is None:
            return self.async_abort(reason="unknown")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        if self.reauth_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge existing config with new credentials
            reauth_data = {**self.reauth_entry.data, **user_input}

            try:
                info = await validate_input(self.hass, reauth_data)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                # Verify the user ID matches to prevent account switching
                if info["user_id"] != self.reauth_entry.unique_id:
                    return self.async_abort(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data_updates=user_input,
                )

        # Show form with existing homeserver and username pre-filled
        reauth_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOMESERVER, default=self.reauth_entry.data[CONF_HOMESERVER]
                ): cv.string,
                vol.Required(
                    CONF_USERNAME, default=self.reauth_entry.data[CONF_USERNAME]
                ): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self.reauth_entry.data.get(CONF_VERIFY_SSL, True),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={
                "username": self.reauth_entry.data[CONF_USERNAME],
                "homeserver": self.reauth_entry.data[CONF_HOMESERVER],
            },
        )
