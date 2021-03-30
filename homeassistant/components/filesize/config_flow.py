"""Config flow for filesize integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
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
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN  # pylint: disable=unused-import

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


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input."""

    if not hass.config.is_allowed_path(data[CONF_FILE_PATH]):
        raise InvalidPath

    try:
        cv.isfile(data[CONF_FILE_PATH])
    except vol.Invalid as ex:
        raise NotAFile from ex

    # Return info that you want to store in the config entry.
    return {"title": f"{data[CONF_FILE_PATH]} ({data[CONF_UNIT_OF_MEASUREMENT]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for filesize."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> dict[str, Any]:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_FILE_PATH]}_{user_input[CONF_UNIT_OF_MEASUREMENT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidPath:  # pylint: disable=broad-except
                errors[CONF_FILE_PATH] = "invalid_path"
            except NotAFile:  # pylint: disable=broad-except
                errors[CONF_FILE_PATH] = "not_a_file"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidPath(exceptions.HomeAssistantError):
    """Error if invalid path provided."""


class NotAFile(exceptions.HomeAssistantError):
    """Error if provided path does not point to a file."""
