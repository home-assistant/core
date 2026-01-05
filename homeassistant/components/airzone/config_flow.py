"""Config flow for Airzone."""

from __future__ import annotations

import logging
from typing import Any

from aioairzone.const import DEFAULT_PORT, DEFAULT_SYSTEM_ID
from aioairzone.exceptions import AirzoneError, InvalidSystem
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)
SYSTEM_ID_SCHEMA = CONFIG_SCHEMA.extend(
    {
        vol.Required(CONF_ID, default=1): int,
    }
)


def short_mac(addr: str) -> str:
    """Convert MAC address to short address."""
    return addr.replace(":", "")[-4:].upper()


class AirZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for an Airzone device."""

    _discovered_ip: str | None = None
    _discovered_mac: str | None = None
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = CONFIG_SCHEMA
        errors = {}

        if user_input is not None:
            if CONF_ID not in user_input:
                user_input[CONF_ID] = DEFAULT_SYSTEM_ID

            self._async_abort_entries_match(user_input)

            airzone = AirzoneLocalApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_ID],
                ),
            )

            try:
                mac = await airzone.validate()
            except InvalidSystem:
                data_schema = SYSTEM_ID_SCHEMA
                errors[CONF_ID] = "invalid_system_id"
            except AirzoneError:
                errors["base"] = "cannot_connect"
            else:
                if mac:
                    await self.async_set_unique_id(
                        format_mac(mac), raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                        }
                    )

                title = f"Airzone {user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                if user_input[CONF_ID] != DEFAULT_SYSTEM_ID:
                    title += f" #{user_input[CONF_ID]}"

                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        self._discovered_ip = discovery_info.ip
        self._discovered_mac = discovery_info.macaddress

        _LOGGER.debug(
            "DHCP discovery detected Airzone WebServer: %s", self._discovered_mac
        )

        self._async_abort_entries_match({CONF_HOST: self._discovered_ip})

        await self.async_set_unique_id(format_mac(self._discovered_mac))
        self._abort_if_unique_id_configured()

        options = ConnectionOptions(self._discovered_ip)
        airzone = AirzoneLocalApi(
            aiohttp_client.async_get_clientsession(self.hass), options
        )
        try:
            await airzone.get_version()
        except (AirzoneError, TimeoutError) as err:
            raise AbortFlow("cannot_connect") from err

        return await self.async_step_discovered_connection()

    async def async_step_discovered_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_ip is not None
        assert self._discovered_mac is not None

        errors = {}
        base_schema = {vol.Required(CONF_PORT, default=DEFAULT_PORT): int}

        if user_input is not None:
            airzone = AirzoneLocalApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(
                    self._discovered_ip,
                    user_input[CONF_PORT],
                    user_input.get(CONF_ID, DEFAULT_SYSTEM_ID),
                ),
            )

            try:
                mac = await airzone.validate()
            except InvalidSystem:
                base_schema[vol.Required(CONF_ID, default=1)] = int
                errors[CONF_ID] = "invalid_system_id"
            except AirzoneError:
                errors["base"] = "cannot_connect"
            else:
                user_input[CONF_HOST] = self._discovered_ip

                if mac is None:
                    mac = self._discovered_mac

                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )

                title = f"Airzone {short_mac(mac)}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="discovered_connection",
            data_schema=vol.Schema(base_schema),
            errors=errors,
        )
