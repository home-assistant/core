"""Config flow for Bbox tests integration."""
from __future__ import annotations

import socket
from typing import Any

import pybbox2
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


def try_login(host, password) -> str | None:
    """Try logging in to device and return any errors."""
    assert host is not None
    assert password is not None

    try:
        bbox = pybbox2.Bbox(api_host=host, password=password)
        result = bbox.do_auth()
    except socket.gaierror:
        return "cannot_connect"
    except (requests.exceptions.ConnectionError, requests.exceptions.SSLError):
        return "cannot_connect"
    except Exception as e:
        if "401" in str(e):
            return "invalid_auth"
        else:
            return "unknown"
    if not result:
        return f"invalid_auth {result}"

    return None


class BboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bbox tests."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._name: str = "Bbox"
        self._host: str | None = None
        self._password: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Hostname is format: bbox.local.
        local_name = discovery_info["hostname"][:-1]
        node_name = local_name[: -len(".local")]
        address = discovery_info["properties"].get("address", local_name)

        # Override host with the known HTTPS domain.
        # self._host = discovery_info[CONF_HOST]
        self._host = "https://mabbox.bytel.fr"
        self._name = node_name

        # Check if already configured
        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        for entry in self._async_current_entries():
            already_configured = False

            if CONF_HOST in entry.data and entry.data[CONF_HOST] in (
                address,
                self._host,
            ):
                # Is this address or IP address already configured?
                already_configured = True

            if already_configured:
                # Backwards compat, we update old entries
                if not entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_HOST: discovery_info[CONF_HOST]},
                        unique_id=node_name,
                    )

                return self.async_abort(reason="already_configured")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._name, "host": self._host},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._password = user_input[CONF_PASSWORD]
            error = await self.hass.async_add_executor_job(
                try_login, self._host, self._password
            )
            if error:
                return await self.async_step_user(error=error)

            await self.async_set_unique_id(self._host)
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_HOST: self._host,
                    CONF_PASSWORD: self._password,
                },
            )

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_PASSWORD, default=self._password): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
