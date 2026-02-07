"""Config flow for Automation Device Specification (ADS) integration."""

from __future__ import annotations

import logging
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 48898


def _base_schema(ads_config: dict[str, Any] | None = None) -> vol.Schema:
    """Generate base schema."""
    if ads_config is None:
        ads_config = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE, default=ads_config.get(CONF_DEVICE, "")
            ): str,
            vol.Optional(
                CONF_IP_ADDRESS, default=ads_config.get(CONF_IP_ADDRESS, "")
            ): str,
            vol.Optional(
                CONF_PORT, default=ads_config.get(CONF_PORT, DEFAULT_PORT)
            ): int,
        }
    )


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from _base_schema with values provided by the user.
    """
    net_id = data[CONF_DEVICE]
    ip_address = data.get(CONF_IP_ADDRESS) or None
    port = data[CONF_PORT]

    # Test the connection
    client = pyads.Connection(net_id, port, ip_address)
    try:
        client.open()
        # Try to read device info to verify connection
        device_info = client.read_device_info()
        client.close()
    except pyads.ADSError as err:
        _LOGGER.error("Failed to connect to ADS device: %s", err)
        raise

    return {"title": f"ADS {net_id}", "device_info": device_info}


def _format_device(user_input: dict[str, Any]) -> str:
    """Format device info for display."""
    net_id = user_input[CONF_DEVICE]
    ip_address = user_input.get(CONF_IP_ADDRESS)
    port = user_input[CONF_PORT]

    if ip_address:
        return f"{net_id} ({ip_address}:{port})"
    return f"{net_id}:{port}"


class AdsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the ADS config flow."""
        self.ads_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except pyads.ADSError as ex:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(ex)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_DEVICE])
                self._abort_if_unique_id_configured()

                title = info["title"]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(self.ads_config),
            errors=errors,
            description_placeholders=description_placeholders,
        )
