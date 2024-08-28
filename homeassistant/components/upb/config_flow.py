"""Config flow for UPB PIM integration."""

import asyncio
from contextlib import suppress
import logging
from typing import Any
from urllib.parse import urlparse

import upb_lib
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_FILE_PATH, CONF_HOST, CONF_PROTOCOL
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PROTOCOL_MAP = {"TCP": "tcp://", "Serial port": "serial://"}
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROTOCOL, default="Serial port"): vol.In(
            ["TCP", "Serial port"]
        ),
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_FILE_PATH, default=""): str,
    }
)
VALIDATE_TIMEOUT = 15


async def _validate_input(data):
    """Validate the user input allows us to connect."""

    def _connected_callback():
        connected_event.set()

    connected_event = asyncio.Event()
    file_path = data.get(CONF_FILE_PATH)
    url = _make_url_from_data(data)

    upb = upb_lib.UpbPim({"url": url, "UPStartExportFile": file_path})

    await upb.async_connect(_connected_callback)

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
    return (upb.network_id, {"title": "UPB", CONF_HOST: url, CONF_FILE_PATH: file_path})


def _make_url_from_data(data):
    if host := data.get(CONF_HOST):
        return host

    protocol = PROTOCOL_MAP[data[CONF_PROTOCOL]]
    address = data[CONF_ADDRESS]
    return f"{protocol}{address}"


class UPBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UPB PIM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                if self._url_already_configured(_make_url_from_data(user_input)):
                    return self.async_abort(reason="already_configured")
                network_id, info = await _validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidUpbFile:
                errors["base"] = "invalid_upb_file"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(network_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: info[CONF_HOST],
                        CONF_FILE_PATH: user_input[CONF_FILE_PATH],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    def _url_already_configured(self, url):
        """See if we already have a UPB PIM matching user input configured."""
        existing_hosts = {
            urlparse(entry.data[CONF_HOST]).hostname
            for entry in self._async_current_entries()
        }
        return urlparse(url).hostname in existing_hosts


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidUpbFile(HomeAssistantError):
    """Error to indicate there is invalid or missing UPB config file."""
