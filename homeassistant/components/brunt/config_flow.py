"""Config flow for brunt integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError
from brunt import BruntClientAsync
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def validate_input(user_input: dict[str, Any]) -> dict[str, str] | None:
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
            _LOGGER.exception("Unknown error when trying to login to Brunt")
            errors = {"base": "unknown"}
    except ServerDisconnectedError:
        _LOGGER.warning("Cannot connect to Brunt")
        errors = {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unknown error when trying to login to Brunt")
        errors = {"base": "unknown"}
    finally:
        await bapi.async_close()
    return errors


class BruntConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brunt."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = await validate_input(user_input)
        if errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data=user_input,
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
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                description_placeholders={"username": username},
            )
        user_input[CONF_USERNAME] = username
        errors = await validate_input(user_input)
        if errors is not None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                errors=errors,
                description_placeholders={"username": username},
            )

        return self.async_update_reload_and_abort(reauth_entry, data=user_input)
