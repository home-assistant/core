"""Adds config flow for OpenEVSE."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from . import test_connection
from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class OpenEVSEFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OpenEVSE."""

    VERSION = 1
    DEFAULTS = {CONF_HOST: DEFAULT_HOST, CONF_NAME: DEFAULT_NAME}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await _start_config_flow(
            self,
            "user",
            user_input[CONF_NAME] if user_input else None,
            user_input,
            self.DEFAULTS,
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "Already configured. This YAML configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")

        import_config.pop("platform", None)
        if CONF_NAME not in import_config:
            import_config[CONF_NAME] = DEFAULT_NAME

        import_config[CONF_NAME] = slugify(import_config[CONF_NAME].lower())
        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the option flow."""
        return OpenEVSEOptionsFlow(config_entry)


class OpenEVSEOptionsFlow(config_entries.OptionsFlow):
    """Options flow for OpenEVSE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await _start_config_flow(
            self,
            "init",
            "",
            user_input,
            self.config_entry.data,
            self.config_entry.entry_id,
        )


def _get_schema(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    default_dict: dict[str, Any],
    entry_id: str = None,
) -> vol.Schema:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> dict[str, Any]:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME, default=_get_default(CONF_NAME, DEFAULT_NAME)
            ): cv.string,
            vol.Required(
                CONF_HOST, default=_get_default(CONF_HOST, DEFAULT_HOST)
            ): cv.string,
            vol.Optional(
                CONF_USERNAME, default=_get_default(CONF_USERNAME, "")
            ): cv.string,
            vol.Optional(
                CONF_PASSWORD, default=_get_default(CONF_PASSWORD, "")
            ): cv.string,
        },
    )


async def _start_config_flow(
    cls: OpenEVSEFlowHandler | OpenEVSEOptionsFlow,
    step_id: str,
    title: str,
    user_input: dict[str, Any],
    defaults: dict[str, Any],
    entry_id: str = None,
):
    """Start a config flow."""
    errors = {}
    if user_input is not None:
        user_input[CONF_NAME] = slugify(user_input[CONF_NAME].lower())
        check, msg = await cls.hass.async_add_executor_job(
            test_connection,
            user_input[CONF_HOST],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )
        if msg == "cannot_connect":
            errors = {CONF_HOST: "cannot_connect"}
        elif msg == "invalid_auth":
            errors = {CONF_USERNAME: "invalid_auth", CONF_PASSWORD: "invalid_auth"}

        if not check:
            return cls.async_show_form(
                step_id=step_id,
                data_schema=_get_schema(cls.hass, user_input, defaults, entry_id),
                errors=errors,
            )

        return cls.async_create_entry(title=title, data=user_input)

    return cls.async_show_form(
        step_id=step_id,
        data_schema=_get_schema(cls.hass, user_input, defaults, entry_id),
        errors=errors,
    )
