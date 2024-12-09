"""Config flow for BSB-Lan integration."""

from __future__ import annotations

import logging
from typing import Any

from bsblan import BSBLAN, BSBLANConfig, BSBLANError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_PASSKEY, DEFAULT_PORT, DOMAIN


class BSBLANFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLAN config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize BSBLan flow."""
        self.host: str | None = None
        self.port: int = DEFAULT_PORT
        self.mac: str | None = None
        self.passkey: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self._discovered_device: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        self.host = user_input[CONF_HOST]
        self.port = user_input[CONF_PORT]
        self.passkey = user_input.get(CONF_PASSKEY)
        self.username = user_input.get(CONF_USERNAME)
        self.password = user_input.get(CONF_PASSWORD)

        return await self._validate_and_create()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""

        self.host = str(
            getattr(discovery_info, "ip_address", None)
            or (discovery_info.ip_addresses[0] if discovery_info.ip_addresses else None)
            or discovery_info.hostname
        )
        self.port = discovery_info.port or DEFAULT_PORT

        # Check if the device is already configured
        for entry in self._async_current_entries():
            if (
                entry.data.get(CONF_HOST) == self.host
                and entry.data.get(CONF_PORT) == self.port
            ):
                return self.async_abort(reason="already_configured")

        # Store discovery info for later use
        self._discovered_device = {
            CONF_HOST: self.host,
            CONF_PORT: self.port,
        }

        # Proceed to get credentials
        self.context["title_placeholders"] = {"name": f"BSBLAN {self.host}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle getting credentials for discovered device."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_PASSKEY): str,
                        vol.Optional(CONF_USERNAME): str,
                        vol.Optional(CONF_PASSWORD): str,
                    }
                ),
                description_placeholders={"host": str(self.host)},
            )

        self.passkey = user_input.get(CONF_PASSKEY)
        self.username = user_input.get(CONF_USERNAME)
        self.password = user_input.get(CONF_PASSWORD)

        return await self._validate_and_create()

    async def _validate_and_create(self) -> ConfigFlowResult:
        """Validate device connection and create entry."""
        try:
            await self._get_bsblan_info()
        except BSBLANError:
            return self._show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    @callback
    def _show_setup_form(self, errors: dict | None = None) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_PASSKEY): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=format_mac(self.mac),
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_PASSKEY: self.passkey,
                CONF_USERNAME: self.username,
                CONF_PASSWORD: self.password,
            },
        )

    async def _get_bsblan_info(self, raise_on_progress: bool = True) -> None:
        """Get device information from a BSBLAN device."""
        logging.debug("Getting device info from BSBLAN device")
        config = BSBLANConfig(
            host=self.host,
            passkey=self.passkey,
            port=self.port,
            username=self.username,
            password=self.password,
        )
        session = async_get_clientsession(self.hass)
        bsblan = BSBLAN(config, session)
        device = await bsblan.device()
        self.mac = device.MAC

        await self.async_set_unique_id(
            format_mac(self.mac), raise_on_progress=raise_on_progress
        )
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
            }
        )
