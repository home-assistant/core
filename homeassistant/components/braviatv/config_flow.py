"""Config flow to configure the Bravia TV integration."""
from __future__ import annotations

from contextlib import suppress
import ipaddress
import re
from typing import Any

from aiohttp import CookieJar
from pybravia import BraviaTV, BraviaTVError, BraviaTVNotSupported
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

from . import BraviaTVCoordinator
from .const import (
    ATTR_CID,
    ATTR_MAC,
    ATTR_MODEL,
    CLIENTID_PREFIX,
    CONF_IGNORED_SOURCES,
    DOMAIN,
    NICKNAME,
)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    with suppress(ValueError):
        if ipaddress.ip_address(host).version in [4, 6]:
            return True
    disallowed = re.compile(r"[^a-zA-Z\d\-]")
    return all(x and not disallowed.search(x) for x in host.split("."))


class BraviaTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BraviaTV integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.client: BraviaTV
        self.host: str
        self.title = ""
        self.mac: str

    async def init_device(self, pin: str) -> None:
        """Initialize Bravia TV device."""
        await self.client.connect(pin=pin, clientid=CLIENTID_PREFIX, nickname=NICKNAME)
        await self.client.set_wol_mode(True)
        system_info = await self.client.get_system_info()

        await self.async_set_unique_id(system_info[ATTR_CID].lower())
        self._abort_if_unique_id_configured()

        self.title = system_info[ATTR_MODEL]
        self.mac = system_info[ATTR_MAC]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BraviaTVOptionsFlowHandler:
        """Bravia TV options callback."""
        return BraviaTVOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if host_valid(user_input[CONF_HOST]):
                session = async_create_clientsession(
                    self.hass,
                    cookie_jar=CookieJar(unsafe=True, quote_cookie=False),
                )
                self.host = user_input[CONF_HOST]
                self.client = BraviaTV(host=self.host, session=session)

                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get PIN from the Bravia TV device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.init_device(user_input[CONF_PIN])
            except BraviaTVNotSupported:
                errors["base"] = "unsupported_model"
            except BraviaTVError:
                errors["base"] = "cannot_connect"
            else:
                user_input[CONF_HOST] = self.host
                user_input[CONF_MAC] = self.mac
                return self.async_create_entry(title=self.title, data=user_input)

        try:
            await self.client.pair(CLIENTID_PREFIX, NICKNAME)
        except BraviaTVError:
            return self.async_abort(reason="no_ip_control")

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({vol.Required(CONF_PIN, default=""): str}),
            errors=errors,
        )


class BraviaTVOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Bravia TV."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Bravia TV options flow."""
        self.config_entry = config_entry
        self.ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES)
        self.source_list: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        coordinator: BraviaTVCoordinator = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]

        await coordinator.async_update_sources()
        sources = coordinator.source_map.values()
        self.source_list = [item.get("title", "") for item in sources]
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORED_SOURCES, default=self.ignored_sources
                    ): cv.multi_select(self.source_list)
                }
            ),
        )
