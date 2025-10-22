"""Config flow for OpenH264 Nedis Camera integration."""
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_ENTITY_ID
from .const import (
    DOMAIN, 
    DEFAULT_NAME, 
    CONF_NAME, 
    CONF_MODE, 
    MODE_CAMERA, 
    MODE_URL,
    CONF_STREAM_URL, 
    CONF_SNAPSHOT_URL,
    CONF_LIB_PATH, 
    CONF_ACCEPT_LICENSE
)

BASE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required(CONF_MODE, default=MODE_CAMERA): vol.In([MODE_CAMERA, MODE_URL]),
})

URL_SCHEMA_EXTRA = vol.Schema({
    vol.Optional(CONF_STREAM_URL): str,
    vol.Optional(CONF_SNAPSHOT_URL): str,
})

CAMERA_SCHEMA_EXTRA = vol.Schema({
    vol.Optional(CONF_ENTITY_ID): str,
})

LIB_SCHEMA_EXTRA = vol.Schema({
    vol.Optional(CONF_LIB_PATH): str,
    vol.Optional(CONF_ACCEPT_LICENSE, default=False): bool,
})


class OpenH264CustomH264ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenH264 Nedis Camera."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            mode = user_input.get(CONF_MODE)
            
            # Validate based on mode
            if mode == MODE_CAMERA and not user_input.get(CONF_ENTITY_ID):
                errors["base"] = "camera_required"
            elif mode == MODE_URL and not (user_input.get(CONF_STREAM_URL) or user_input.get(CONF_SNAPSHOT_URL)):
                errors["base"] = "url_required"
            
            if not errors:
                title = user_input.get(CONF_NAME) or DEFAULT_NAME
                return self.async_create_entry(title=title, data=user_input)

        # Build schema dynamically based on mode selection
        schema = BASE_SCHEMA
        
        # Add mode-specific fields
        if (user_input or {}).get(CONF_MODE, MODE_CAMERA) == MODE_URL:
            schema = schema.extend(URL_SCHEMA_EXTRA.schema)
        else:
            schema = schema.extend(CAMERA_SCHEMA_EXTRA.schema)
        
        # Add library configuration fields
        schema = schema.extend(LIB_SCHEMA_EXTRA.schema)
        
        return self.async_show_form(
            step_id="user", 
            data_schema=schema, 
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OpenH264CustomH264OptionsFlow(config_entry)


class OpenH264CustomH264OptionsFlow(config_entries.OptionsFlow):
    """Handle OpenH264 Nedis Camera options."""

    def __init__(self, config_entry):
        """Initialize OpenH264 options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Combine data and options for defaults
        data = {**self.config_entry.data, **self.config_entry.options}
        
        schema = vol.Schema({
            vol.Optional(CONF_LIB_PATH, default=data.get(CONF_LIB_PATH, "")): str,
            vol.Optional(CONF_ACCEPT_LICENSE, default=data.get(CONF_ACCEPT_LICENSE, False)): bool,
        })
        
        return self.async_show_form(step_id="init", data_schema=schema)
