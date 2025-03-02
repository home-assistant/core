"""The filesize config flow."""

from __future__ import annotations

import logging
import pathlib
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_FILE_PATH): str})

_LOGGER = logging.getLogger(__name__)


def validate_path(hass: HomeAssistant, path: str) -> tuple[str | None, dict[str, str]]:
    """Validate path."""
    get_path = pathlib.Path(path)
    if not get_path.exists() or not get_path.is_file():
        _LOGGER.error("Can not access file %s", path)
        return (None, {"base": "not_valid"})

    if not hass.config.is_allowed_path(path):
        _LOGGER.error("Filepath %s is not allowed", path)
        return (None, {"base": "not_allowed"})

    full_path = get_path.absolute()

    return (str(full_path), {})


class FilesizeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Filesize."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            full_path, errors = await self.hass.async_add_executor_job(
                validate_path, self.hass, user_input[CONF_FILE_PATH]
            )
            if not errors:
                await self.async_set_unique_id(full_path)
                self._abort_if_unique_id_configured()

                name = str(user_input[CONF_FILE_PATH]).rsplit("/", maxsplit=1)[-1]
                return self.async_create_entry(
                    title=name,
                    data={CONF_FILE_PATH: user_input[CONF_FILE_PATH]},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reconfigure_entry = self._get_reconfigure_entry()
            full_path, errors = await self.hass.async_add_executor_job(
                validate_path, self.hass, user_input[CONF_FILE_PATH]
            )
            if not errors:
                await self.async_set_unique_id(full_path)
                self._abort_if_unique_id_configured()

                name = str(user_input[CONF_FILE_PATH]).rsplit("/", maxsplit=1)[-1]
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=name,
                    unique_id=self.unique_id,
                    data_updates={CONF_FILE_PATH: user_input[CONF_FILE_PATH]},
                )

        return self.async_show_form(
            step_id="reconfigure", data_schema=DATA_SCHEMA, errors=errors
        )
