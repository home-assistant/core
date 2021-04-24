"""Config flow for motionEye integration."""
from __future__ import annotations

import logging
from typing import Any

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_REAUTH,
    ConfigFlow,
)
from homeassistant.const import CONF_SOURCE, CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import create_motioneye_client
from .const import (  # pylint:disable=unused-import
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CONFIG_ENTRY,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MotionEyeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for motionEye."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: ConfigType | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""

        def _get_form(
            user_input: ConfigType | None, errors: dict[str, str] | None = None
        ) -> dict[str, Any]:
            """Show the form to the user."""
            out = self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_URL, default=user_input.get(CONF_URL, "")
                        ): str,
                        vol.Optional(
                            CONF_ADMIN_USERNAME,
                            default=user_input.get(CONF_ADMIN_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_ADMIN_PASSWORD,
                            default=user_input.get(CONF_ADMIN_PASSWORD),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_USERNAME,
                            default=user_input.get(CONF_SURVEILLANCE_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_PASSWORD,
                            default=user_input.get(CONF_SURVEILLANCE_PASSWORD),
                        ): str,
                    }
                ),
                errors=errors,
            )
            return out

        out: dict[str, Any] = {}
        if user_input is None:
            entry = self.context.get(CONF_CONFIG_ENTRY)
            return _get_form(entry.data if entry else {})

        try:
            # Cannot use cv.url validation in the schema itself, so
            # apply extra validation here.
            cv.url(user_input[CONF_URL])
        except vol.Invalid:
            return _get_form(user_input, {"base": "invalid_url"})

        client = create_motioneye_client(
            user_input[CONF_URL],
            admin_username=user_input.get(CONF_ADMIN_USERNAME),
            admin_password=user_input.get(CONF_ADMIN_PASSWORD),
            surveillance_username=user_input.get(CONF_SURVEILLANCE_USERNAME),
            surveillance_password=user_input.get(CONF_SURVEILLANCE_PASSWORD),
        )

        try:
            await client.async_client_login()
        except MotionEyeClientConnectionError:
            return _get_form(user_input, {"base": "cannot_connect"})
        except MotionEyeClientInvalidAuthError:
            return _get_form(user_input, {"base": "invalid_auth"})
        except MotionEyeClientRequestError:
            return _get_form(user_input, {"base": "unknown"})
        finally:
            await client.async_client_close()

        if (
            self.context.get(CONF_SOURCE) == SOURCE_REAUTH
            and self.context.get(CONF_CONFIG_ENTRY) is not None
        ):
            entry = self.context[CONF_CONFIG_ENTRY]
            self.hass.config_entries.async_update_entry(entry, data=user_input)
            # Need to manually reload, as the listener won't have been
            # installed because the initial load did not succeed (the reauth
            # flow will not be initiated if the load succeeds).
            await self.hass.config_entries.async_reload(entry.entry_id)
            out = self.async_abort(reason="reauth_successful")
            return out

        # Search for duplicates: there isn't a useful unique_id, but
        # at least prevent entries with the same motionEye URL.
        for existing_entry in self.hass.config_entries.async_entries(DOMAIN):
            if existing_entry.data.get(CONF_URL) == user_input[CONF_URL]:
                return self.async_abort(reason="already_configured")

        out = self.async_create_entry(
            title=f"{user_input[CONF_URL]}",
            data=user_input,
        )
        return out

    async def async_step_reauth(
        self,
        config_data: ConfigType | None = None,
    ) -> dict[str, Any]:
        """Handle a reauthentication flow."""
        return await self.async_step_user(config_data)
