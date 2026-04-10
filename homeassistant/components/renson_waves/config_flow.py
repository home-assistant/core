"""Config flow for Renson WAVES."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import RensonWavesCannotConnect, RensonWavesClient
from .const import DEFAULT_PORT, DOMAIN


class RensonWavesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Renson WAVES."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._device_serial: str | None = None
        self._device_name: str | None = None
        self._host: str | None = None
        self._port = DEFAULT_PORT

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            try:
                await self._async_probe_device(host, port)

                await self.async_set_unique_id(self._device_serial or f"{host}:{port}")
                self._abort_if_unique_id_configured()

                return await self.async_step_confirm()
            except RensonWavesCannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle confirm step."""
        if user_input is None:
            self._set_confirm_only()
            placeholders = {"name": self._device_name or "Renson WAVES"}
            self.context["title_placeholders"] = placeholders
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=placeholders,
            )

        assert self._host is not None

        return self.async_create_entry(
            title=self._device_name or "Renson WAVES",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
            },
        )

    async def _async_probe_device(self, host: str, port: int) -> None:
        """Probe device to get serial and name."""
        session = async_get_clientsession(self.hass)
        client = RensonWavesClient(host, port, session)

        constellation = await client.async_get_constellation()

        global_data = constellation.get("global", {})
        self._device_serial = (
            global_data.get("serial", {}).get("value") or f"{host}:{port}"
        )
        self._device_name = (
            global_data.get("device_name", {}).get("value") or "Renson WAVES"
        )
        self._host = host
        self._port = port
