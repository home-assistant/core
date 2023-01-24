"""Support for Devialet Phantom speakers."""
from __future__ import annotations

import logging
from typing import Any

from devialet.devialet_api import DevialetApi
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

LOGGER = logging.getLogger(__package__)


class DevialetFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Devialet."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._model: str | None = None
        self._serial: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._host = user_input[CONF_HOST]
            client = DevialetApi(self._host, session)

            if not await client.async_update() or client.serial is None:
                errors["base"] = "cannot_connect"
                LOGGER.error("Cannot connect")
            else:
                await self.async_set_unique_id(client.serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=client.device_name,
                    data={CONF_HOST: self._host, CONF_NAME: client.device_name},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        LOGGER.info("Devialet device found via ZEROCONF: %s", discovery_info)

        self._host = discovery_info.host
        self._name = discovery_info.name.split(".", 1)[0]
        self._model = discovery_info.properties["model"]
        self._serial = discovery_info.properties["serialNumber"]

        await self.async_set_unique_id(self._serial)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"title": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        errors = {}
        title = f"{self._name} ({self._model})"

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = DevialetApi(self._host, session)

            if not await api.async_update():
                errors["base"] = "cannot_connect"
                LOGGER.error("Cannot connect")
            else:
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: self._host, CONF_NAME: self._name},
                )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"device": self._model, "title": title},
            errors=errors,
            last_step=True,
        )
