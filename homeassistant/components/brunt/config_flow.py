"""Config flow for brunt integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError
from brunt import BruntClientAsync
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def validate_input(
    user_input: dict[str, Any]
) -> dict[str, str] | None:  # pragma: no cover
    """Login to the brunt api and return errors if any."""
    errors = None
    bapi = BruntClientAsync(
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )
    try:
        await bapi.async_login()
    except ClientResponseError as exc:
        if exc.status == 403:
            _LOGGER.warning("Brunt Credentials are incorrect")
            errors = {"base": "invalid_auth"}
        else:
            _LOGGER.exception("Unknown error when connecting to Brunt: %s", exc)
            errors = {"base": "unknown"}
    except ServerDisconnectedError:
        _LOGGER.warning("Cannot connect to Brunt")
        errors = {"base": "cannot_connect"}
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown error when connecting to Brunt: %s", exc)
        errors = {"base": "unknown"}
    finally:
        await bapi.async_close()
    return errors


class BruntConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brunt."""

    VERSION = 1

    def __init__(self):
        """Start the Brunt config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = await validate_input(user_input)
        if errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data=user_input,
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        """Handle the reauth step."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if user_input is None:
            return self.async_show_form(step_id="reauth", data_schema=REAUTH_SCHEMA)
        user_input[CONF_USERNAME] = self._reauth_entry.data[CONF_USERNAME]

        errors = await validate_input(user_input)
        if errors is not None:
            return self.async_show_form(
                step_id="reauth", data_schema=REAUTH_SCHEMA, errors=errors
            )

        self.hass.config_entries.async_update_entry(self._reauth_entry, data=user_input)
        await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)

        return self.async_abort(reason="reauth_successful")

    async def async_step_import(self, import_config: dict[str, Any]):
        """Import config from configuration.yaml."""
        entries = self._async_current_entries()
        for entry in entries:
            if entry.data[CONF_USERNAME] == import_config[CONF_USERNAME]:
                return self.async_abort(reason="already_configured_account")

        return await self.async_step_user(import_config)
