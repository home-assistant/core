"""Adds config flow for Bravia TV integration."""
from __future__ import annotations

from contextlib import suppress
import ipaddress
import re
from typing import Any

from bravia_tv import BraviaRC
from bravia_tv.braviarc import NoIPControl
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

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
        self.braviarc: BraviaRC | None = None
        self.host: str | None = None
        self.title = ""
        self.mac: str | None = None

    async def init_device(self, pin: str) -> None:
        """Initialize Bravia TV device."""
        assert self.braviarc is not None
        await self.hass.async_add_executor_job(
            self.braviarc.connect, pin, CLIENTID_PREFIX, NICKNAME
        )

        connected = await self.hass.async_add_executor_job(self.braviarc.is_connected)
        if not connected:
            raise CannotConnect()

        system_info = await self.hass.async_add_executor_job(
            self.braviarc.get_system_info
        )
        if not system_info:
            raise ModelNotSupported()

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
                self.host = user_input[CONF_HOST]
                self.braviarc = BraviaRC(self.host)

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
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except ModelNotSupported:
                errors["base"] = "unsupported_model"
            else:
                user_input[CONF_HOST] = self.host
                user_input[CONF_MAC] = self.mac
                return self.async_create_entry(title=self.title, data=user_input)
        # Connecting with th PIN "0000" to start the pairing process on the TV.
        try:
            assert self.braviarc is not None
            await self.hass.async_add_executor_job(
                self.braviarc.connect, "0000", CLIENTID_PREFIX, NICKNAME
            )
        except NoIPControl:
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
        self.pin = config_entry.data[CONF_PIN]
        self.ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES)
        self.source_list: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
        braviarc = coordinator.braviarc
        connected = await self.hass.async_add_executor_job(braviarc.is_connected)
        if not connected:
            await self.hass.async_add_executor_job(
                braviarc.connect, self.pin, CLIENTID_PREFIX, NICKNAME
            )

        content_mapping = await self.hass.async_add_executor_job(
            braviarc.load_source_list
        )
        self.source_list = {item: item for item in [*content_mapping]}
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class ModelNotSupported(exceptions.HomeAssistantError):
    """Error to indicate not supported model."""
