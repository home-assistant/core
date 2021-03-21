"""Config flow for motionEye integration."""
from __future__ import annotations

import logging
from typing import Any

from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientConnectionFailure,
    MotionEyeClientInvalidAuth,
    MotionEyeClientRequestFailed,
)
from motioneye_client.const import DEFAULT_PORT
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_REAUTH,
    ConfigFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE
from homeassistant.helpers.typing import ConfigType

from . import get_motioneye_config_unique_id
from .const import (  # pylint:disable=unused-import
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_ADMIN_USERNAME): str,
        vol.Optional(CONF_ADMIN_PASSWORD): str,
        vol.Optional(CONF_SURVEILLANCE_USERNAME): str,
        vol.Optional(CONF_SURVEILLANCE_PASSWORD): str,
    }
)


class MotionEyeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for motionEye."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: ConfigType | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        client = MotionEyeClient(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            admin_username=user_input.get(CONF_ADMIN_USERNAME),
            admin_password=user_input.get(CONF_ADMIN_PASSWORD),
            surveillance_username=user_input.get(CONF_SURVEILLANCE_USERNAME),
            surveillance_password=user_input.get(CONF_SURVEILLANCE_PASSWORD),
        )

        unique_id = get_motioneye_config_unique_id(
            user_input[CONF_HOST], user_input[CONF_PORT]
        )
        entry = await self.async_set_unique_id(unique_id, raise_on_progress=False)

        try:
            await client.async_client_login()
        except MotionEyeClientConnectionFailure:
            errors["base"] = "cannot_connect"
        except MotionEyeClientInvalidAuth:
            errors["base"] = "invalid_auth"
        except MotionEyeClientRequestFailed:
            errors["base"] = "unknown"
        else:
            if self.context.get(CONF_SOURCE) == SOURCE_REAUTH and entry is not None:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                # Need to manually reload, as the listener won't have been installed because
                # the initial load did not succeed (the reauth flow will not be initiated if
                # the load succeeds).
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(
                title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self,
        config_data: ConfigType | None = None,
    ) -> dict[str, Any]:
        """Handle a reauthentication flow."""
        return await self.async_step_user(config_data)
