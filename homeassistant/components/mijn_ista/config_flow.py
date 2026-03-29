"""Config flow for mijn.ista.nl integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from mijn_ista_api import MijnIstaAPI, MijnIstaAuthError, MijnIstaConnectionError
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)

_STEP_USER_SCHEMA = _CREDENTIALS_SCHEMA.extend(
    {
        vol.Required(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): NumberSelector(
            NumberSelectorConfig(mode=NumberSelectorMode.SLIDER, min=1, max=24, step=1)
        ),
    }
)


async def _validate_credentials(
    hass: Any, username: str, password: str
) -> tuple[str | None, str | None]:
    """Authenticate and return (display_name, error_key)."""
    session = async_get_clientsession(hass)
    api = MijnIstaAPI(session, username, password)
    try:
        await api.authenticate()
        user_data = await api.get_user_values()
        return user_data.get("DisplayName") or username, None
    except MijnIstaAuthError:
        return None, "invalid_auth"
    except MijnIstaConnectionError:
        return None, "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during mijn.ista.nl credential validation")
        return None, "unknown"


class MijnIstaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mijn.ista.nl."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return MijnIstaOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            display_name, error = await _validate_credentials(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"ista NL — {display_name}",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL]),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Allow the user to update their credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            _, error = await _validate_credentials(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _CREDENTIALS_SCHEMA,
                {CONF_USERNAME: reconfigure_entry.data[CONF_USERNAME]},
            ),
            errors=errors,
        )


class MijnIstaOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle options flow for mijn.ista.nl."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL])},
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=self.options.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=1, max=24, step=1
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
