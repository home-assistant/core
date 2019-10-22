"""Config flow to configure the AIS Drive Service component."""

import voluptuous as vol
import logging
import asyncio
import time
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_TYPE, CONF_USERNAME
from homeassistant.core import callback
from .const import DOMAIN, CONF_OAUTH_JSON
import json

_LOGGER = logging.getLogger(__name__)
DRIVE_NAME_INPUT = None
DRIVE_TYPE_INPUT = None
AUTH_URL = None
G_DRIVE_CREATION_TIME_CALL = None


@callback
def configured_drivers(hass):
    """Return a set of configured Drives instances."""
    return set(
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class DriveFlowHandler(config_entries.ConfigFlow):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_oauth(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_oauth(self, user_input=None):
        """Handle a flow start."""
        global AUTH_URL
        errors = {}
        description_placeholders = {"error_info": ""}
        data_schema = vol.Schema({vol.Required(CONF_OAUTH_JSON): str})
        if user_input is not None:
            oauth_json = user_input.get(CONF_OAUTH_JSON)

            try:
                json.loads(oauth_json)
            except ValueError as e:
                errors = {CONF_OAUTH_JSON: "oauth_error"}
                description_placeholders = {"error_info": str(e)}

            if errors == {}:
                # get url from google home
                from homeassistant.components.ais_google_home import (
                    google_home_get_auth_url,
                )

                AUTH_URL = google_home_get_auth_url(oauth_json)
                return await self.async_step_token(user_input=None)

        return self.async_show_form(
            step_id="oauth",
            errors=errors,
            data_schema=data_schema,
            description_placeholders=description_placeholders,
        )

    async def async_step_token(self, user_input=None):
        """Handle a flow start."""
        from homeassistant.components.ais_drives_service import rclone_set_auth_gdrive

        errors = {}
        global G_DRIVE_CREATION_TIME_CALL
        data_schema = vol.Schema({vol.Required("token_key"): str})
        ret = ""
        if user_input is not None and "token_key" in user_input:
            # add new one
            user_input[CONF_NAME] = DRIVE_NAME_INPUT
            user_input[CONF_TYPE] = DRIVE_TYPE_INPUT
            ret = rclone_set_auth_gdrive(DRIVE_NAME_INPUT, user_input["token_key"])
            if ret == "ok":
                # remove if exists
                G_DRIVE_CREATION_TIME_CALL = time.time()
                exists_entries = [
                    entry.entry_id for entry in self._async_current_entries()
                ]
                if exists_entries:
                    await asyncio.wait(
                        [
                            self.hass.config_entries.async_remove(entry_id)
                            for entry_id in exists_entries
                        ]
                    )
                return self.async_create_entry(title="Zdalne dyski", data=user_input)
            else:
                errors = {"token_key": "token_error"}

        return self.async_show_form(
            step_id="token",
            errors=errors,
            description_placeholders={"auth_url": AUTH_URL},
            data_schema=data_schema,
        )
