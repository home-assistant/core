"""Config flow for Philips Air Purifier integration."""
from __future__ import annotations

import logging
from typing import Any

from aioairctrl import CoAPClient
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import COAP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class PurifierHub:
    """PurifierHub connects to the purifier and returns device ID and name."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def test_connection(self) -> dict[str, str]:
        """Test if we can connect to the purifier by requesting it's status."""

        try:
            async with async_timeout.timeout(20):
                client = await CoAPClient.create(host=self.host, port=COAP_PORT)
                try:
                    status = await client.get_status()
                finally:
                    await client.shutdown()
        except Exception as ex:
            _LOGGER.error("Philips Air Purifier: Failed to connect: %s", repr(ex))
            raise CannotConnect() from ex

        if "DeviceId" in status and "name" in status:
            return {
                "name": status["name"],
                "device_id": status["DeviceId"],
                "model": status["modelid"],
            }

        raise CannotConnect()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect and fetch information about the device.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = PurifierHub(data["host"])
    info = await hub.test_connection()
    return info


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips Air Purifier."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["device_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["name"],
                data={"host": user_input["host"], "model": info["model"]},
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
