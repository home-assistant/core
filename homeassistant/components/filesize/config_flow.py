"""The filesize config flow."""
from __future__ import annotations

import logging
import pathlib
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_UNIT_OF_MEASUREMENT,
    DATA_BYTES,
    DATA_EXABYTES,
    DATA_EXBIBYTES,
    DATA_GIBIBYTES,
    DATA_GIGABYTES,
    DATA_KIBIBYTES,
    DATA_KILOBYTES,
    DATA_MEBIBYTES,
    DATA_MEGABYTES,
    DATA_PEBIBYTES,
    DATA_PETABYTES,
    DATA_TEBIBYTES,
    DATA_TERABYTES,
    DATA_YOBIBYTES,
    DATA_YOTTABYTES,
    DATA_ZEBIBYTES,
    DATA_ZETTABYTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

UNIT_OF_MEASUREMENTS = {
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
    DATA_TERABYTES,
    DATA_PETABYTES,
    DATA_EXABYTES,
    DATA_ZETTABYTES,
    DATA_YOTTABYTES,
    DATA_KIBIBYTES,
    DATA_MEBIBYTES,
    DATA_GIBIBYTES,
    DATA_TEBIBYTES,
    DATA_PEBIBYTES,
    DATA_EXBIBYTES,
    DATA_ZEBIBYTES,
    DATA_YOBIBYTES,
}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILE_PATH): str,
        vol.Required(CONF_UNIT_OF_MEASUREMENT, default=DATA_MEGABYTES): vol.In(
            UNIT_OF_MEASUREMENTS
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


def validate_path(hass: HomeAssistant, path: str) -> pathlib.Path:
    """Validate path."""
    try:
        get_path = pathlib.Path(path)
    except OSError as error:
        _LOGGER.error("Cannot access file %s, error %s", path, error)
        raise NotValidError from error

    if not hass.config.is_allowed_path(path):
        _LOGGER.error("File path %s is not valid or allowed", path)
        raise NotAllowedError

    return get_path


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
                get_path = validate_path(self.hass, user_input[CONF_FILE_PATH])
            except NotValidError:
                errors["base"] = "not_valid"
            except NotAllowedError:
                errors["base"] = "not_allowed"
            else:
                fullpath = str(get_path.absolute())
                unique_id = f"{fullpath}_{user_input[CONF_UNIT_OF_MEASUREMENT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                name = str(user_input[CONF_FILE_PATH]).rsplit("/", maxsplit=1)[-1]
                return self.async_create_entry(
                    title=f"{name} ({user_input[CONF_UNIT_OF_MEASUREMENT]})",
                    data={
                        CONF_FILE_PATH: user_input[CONF_FILE_PATH],
                        CONF_UNIT_OF_MEASUREMENT: user_input[CONF_UNIT_OF_MEASUREMENT],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)


class NotValidError(Exception):
    """Path is not valid error."""


class NotAllowedError(Exception):
    """Path is not allowed error."""
