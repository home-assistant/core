"""Config flow for FYTA integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import FytaConfigEntry
from .const import CONF_EXPIRATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)


class FytaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fyta."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize FytaConfigFlow."""
        self.credentials: dict[str, Any] = {}
        self._entry: FytaConfigEntry | None = None

    async def async_auth(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Reusable Auth Helper."""
        fyta = FytaConnector(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

        try:
            self.credentials = await fyta.login()
        except FytaConnectionError:
            return {"base": "cannot_connect"}
        except FytaAuthentificationError:
            return {"base": "invalid_auth"}
        except FytaPasswordError:
            return {"base": "invalid_auth", CONF_PASSWORD: "password_error"}
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(e)
            return {"base": "unknown"}
        finally:
            await fyta.client.close()

        self.credentials[CONF_EXPIRATION] = self.credentials[
            CONF_EXPIRATION
        ].isoformat()

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            if not (errors := await self.async_auth(user_input)):
                user_input |= self.credentials
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}
        assert self._entry is not None

        if user_input and not (errors := await self.async_auth(user_input)):
            user_input |= self.credentials
            return self.async_update_reload_and_abort(
                self._entry, data={**self._entry.data, **user_input}
            )

        data_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA,
            {CONF_USERNAME: self._entry.data[CONF_USERNAME], **(user_input or {})},
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
        )
