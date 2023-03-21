"""Config flow for Solvis Remote integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import ParseResult, urlparse

import defusedxml
import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import HTTPError, Timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host
        self.url = ""

    async def validate_host(self) -> bool:
        """Test if given host responses to http get request in any way."""
        url = urlparse(self.host, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        self.url = ParseResult("http", netloc, path, *url[3:]).geturl()

        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code in (401, 200):  # OK, this is expected
                return True
        except Timeout as err:
            _LOGGER.debug("""GET Request: Timeout Exception -- %s""", err)
        except HTTPError as err:
            _LOGGER.debug("""GET Request: HTTP Exception -- %s""", err)

        return False

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            basic = HTTPDigestAuth(username, password)
            response = requests.get(self.url, stream=True, auth=basic, timeout=10)
            if response.status_code == 200:  # OK, got something
                return True
        except Timeout as err:
            _LOGGER.debug("""GET Request: Timeout Exception -- %s""", err)
        except HTTPError as err:
            _LOGGER.debug("""GET Request: HTTP Exception -- %s""", err)

        return False

    async def validate_uri(self, username: str, password: str) -> bool:
        """Test if we can read from solvis remote the sc2_val.xml file."""
        uri = """{self.url}/sc2_val.xml"""
        try:
            basic = HTTPDigestAuth(username, password)
            response = requests.get(uri, stream=True, auth=basic, timeout=10)
        except Timeout as err:
            _LOGGER.debug("""GET Request: Timeout Exception -- %s""", err)
            return False
        except HTTPError as err:
            _LOGGER.debug("""GET Request: HTTP Exception -- %s""", err)
            return False

        if response.status_code == 200:  # OK, got something
            response.raw.decode_content = True

            sc2_data = defusedxml.ElementTree.parse(response.raw)
            root = sc2_data.getroot()
            payload_data = root.find("data")
            if payload_data is not None:
                return True

        return False


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = PlaceholderHub(data["host"])

    if not await hub.validate_host():
        raise CannotConnect

    if not await hub.authenticate(data["username"], data["password"]):
        raise InvalidAuth

    if not await hub.validate_uri(data["username"], data["password"]):
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": "Solvis Remote"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solvis Heating."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
