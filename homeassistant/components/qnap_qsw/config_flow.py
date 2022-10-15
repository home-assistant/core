"""Config flow for QNAP QSW."""
from __future__ import annotations

import logging
from typing import Any

from aioqsw.exceptions import LoginError, QswError
from aioqsw.localapi import ConnectionOptions, QnapQswApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for a QNAP QSW device."""

    _discovered_mac: str | None = None
    _discovered_url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            qsw = QnapQswApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(url, username, password),
            )

            try:
                system_board = await qsw.validate()
            except LoginError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except QswError:
                errors[CONF_URL] = "cannot_connect"
            else:
                mac = system_board.get_mac()
                if mac is None:
                    raise AbortFlow("invalid_id")

                await self.async_set_unique_id(format_mac(mac), raise_on_progress=False)
                self._abort_if_unique_id_configured()

                title = f"QNAP {system_board.get_product()} {mac}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        self._discovered_url = f"http://{discovery_info.ip}"
        self._discovered_mac = discovery_info.macaddress

        _LOGGER.debug("DHCP discovery detected QSW: %s", self._discovered_mac)

        options = ConnectionOptions(self._discovered_url, "", "")
        qsw = QnapQswApi(aiohttp_client.async_get_clientsession(self.hass), options)

        try:
            await qsw.get_live()
        except QswError as err:
            raise AbortFlow("cannot_connect") from err

        await self.async_set_unique_id(format_mac(self._discovered_mac))
        self._abort_if_unique_id_configured()

        return await self.async_step_discovered_connection()

    async def async_step_discovered_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        errors = {}
        assert self._discovered_url is not None

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            qsw = QnapQswApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(self._discovered_url, username, password),
            )

            try:
                system_board = await qsw.validate()
            except LoginError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except QswError:
                errors["base"] = "cannot_connect"
            else:
                title = f"QNAP {system_board.get_product()} {self._discovered_mac}"
                user_input[CONF_URL] = self._discovered_url
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="discovered_connection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
