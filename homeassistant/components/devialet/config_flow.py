"""Support for Devialet Phantom speakers."""

from __future__ import annotations

import logging
from typing import Any

from devialet.devialet_api import DevialetApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

LOGGER = logging.getLogger(__package__)


class DevialetFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Devialet."""

    VERSION = 1

    _host: str
    _model: str
    _name: str
    _serial: str

    def __init__(self) -> None:
        """Initialize flow."""
        self._errors: dict[str, str] = {}

    async def async_validate_input(self) -> ConfigFlowResult | None:
        """Validate the input using the Devialet API."""

        self._errors.clear()
        session = async_get_clientsession(self.hass)
        client = DevialetApi(self._host, session)

        if not await client.async_update() or client.serial is None:
            self._errors["base"] = "cannot_connect"
            LOGGER.error("Cannot connect")
            return None

        await self.async_set_unique_id(client.serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=client.device_name,
            data={CONF_HOST: self._host, CONF_NAME: client.device_name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user or zeroconf."""

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            result = await self.async_validate_input()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=self._errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        LOGGER.debug("Devialet device found via ZEROCONF: %s", discovery_info)

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
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        title = f"{self._name} ({self._model})"

        if user_input is not None:
            result = await self.async_validate_input()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"device": self._model, "title": title},
            errors=self._errors,
            last_step=True,
        )
