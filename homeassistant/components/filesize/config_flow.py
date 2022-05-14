"""The filesize config flow."""
from __future__ import annotations

import logging
import pathlib
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_FILE_PATH): str})

_LOGGER = logging.getLogger(__name__)


def validate_path(hass: HomeAssistant, path: str) -> str:
    """Validate path."""
    get_path = pathlib.Path(path)
    if not get_path.exists() or not get_path.is_file():
        _LOGGER.error("Can not access file %s", path)
        raise NotValidError

    if not hass.config.is_allowed_path(path):
        _LOGGER.error("Filepath %s is not allowed", path)
        raise NotAllowedError

    full_path = get_path.absolute()

    return str(full_path)


class FilesizeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Filesize."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, Any] = {}

        if user_input is not None:
            try:
                full_path = validate_path(self.hass, user_input[CONF_FILE_PATH])
            except NotValidError:
                errors["base"] = "not_valid"
            except NotAllowedError:
                errors["base"] = "not_allowed"
            else:
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


class NotValidError(HomeAssistantError):
    """Path is not valid error."""


class NotAllowedError(HomeAssistantError):
    """Path is not allowed error."""
