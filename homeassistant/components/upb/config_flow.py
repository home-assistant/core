"""Config flow for UPB PIM integration."""

import asyncio
from contextlib import suppress
import logging
from typing import Any

import upb_lib
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_FILE_PATH
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SerialPortSelector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_FILE_PATH, default=""): str,
    }
)

VALIDATE_TIMEOUT = 15


async def _validate_input(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate the user input allows us to connect."""

    def _connected_callback():
        connected_event.set()

    connected_event = asyncio.Event()
    file_path = data.get(CONF_FILE_PATH)
    url = data[CONF_DEVICE]

    upb = upb_lib.UpbPim({"url": url, "UPStartExportFile": file_path})
    upb.add_handler("connected", _connected_callback)
    await upb.load_upstart_file()
    await upb.async_connect()

    if not upb.config_ok:
        _LOGGER.error("Missing or invalid UPB file: %s", file_path)
        raise InvalidUpbFile

    with suppress(TimeoutError):
        async with asyncio.timeout(VALIDATE_TIMEOUT):
            await connected_event.wait()

    upb.disconnect()

    if not connected_event.is_set():
        _LOGGER.error(
            "Timed out after %d seconds trying to connect with UPB PIM at %s",
            VALIDATE_TIMEOUT,
            url,
        )
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return (
        upb.network_id,
        {"title": "UPB", CONF_DEVICE: url, CONF_FILE_PATH: file_path},
    )


class UPBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UPB PIM."""

    VERSION = 1
    MINOR_VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            try:
                network_id, info = await _validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidUpbFile:
                errors["base"] = "invalid_upb_file"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(str(network_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_DEVICE: info[CONF_DEVICE],
                        CONF_FILE_PATH: info[CONF_FILE_PATH],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidUpbFile(HomeAssistantError):
    """Error to indicate there is invalid or missing UPB config file."""
