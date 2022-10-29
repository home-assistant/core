"""Config flow for TP-Link Omada integration."""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from tplink_omada_client.exceptions import (
    ConnectionFailed,
    OmadaClientException,
    RequestFailed,
    UnsupportedControllerVersion,
)
from tplink_omada_client.omadaclient import OmadaClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required("site", default="Default"): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class OmadaHub:
    """Omada Controller hub."""

    def __init__(self, hass: HomeAssistant, data: MappingProxyType[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self.host = data[CONF_HOST]
        self.site = data["site"]
        self.verify_ssl = bool(data[CONF_VERIFY_SSL])
        self.username = data[CONF_USERNAME]
        self.password = data[CONF_PASSWORD]
        self.client = None

    async def get_client(self) -> OmadaClient:
        """Get the client api for the hub."""
        if not self.client:
            websession = async_get_clientsession(self.hass, verify_ssl=self.verify_ssl)
            self.client = OmadaClient(
                self.host,
                self.username,
                self.password,
                websession=websession,
                site=self.site,
            )
        return self.client

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""

        client = await self.get_client()
        await client.login()

        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    hub = OmadaHub(hass, MappingProxyType(data))

    await hub.authenticate()

    # Return info that you want to store in the config entry.
    return {"title": f"Omada Controller ({data['site']})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TP-Link Omada."""

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
        except ConnectionFailed:
            errors["base"] = "cannot_connect"
        except RequestFailed:
            errors["base"] = "invalid_auth"
        except UnsupportedControllerVersion:
            errors["base"] = "unsupported_controller"
        except OmadaClientException:
            errors["base"] = "unknown"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
