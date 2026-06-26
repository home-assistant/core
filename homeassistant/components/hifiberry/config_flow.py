"""Config flow for the HiFiBerry integration."""

import logging
from typing import Any, override

from aiohifiberry import AudioControlClient, AudioControlError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> vol.Schema:
    """Return the config flow schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
        }
    )


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""
    client = AudioControlClient(async_get_clientsession(hass), host, port)

    try:
        await client.async_validate()
    except AudioControlError as error:
        raise CannotConnect from error


class HiFiBerryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HiFiBerry."""

    VERSION = 2

    _host: str = DEFAULT_HOST
    _port: int = DEFAULT_PORT

    @callback
    def _async_get_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=self._host,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
            },
        )

    async def _set_unique_id_and_abort(self) -> None:
        """Set unique ID and abort if already configured."""
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]

            try:
                await validate_input(self.hass, self._host, self._port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self._set_unique_id_and_abort()
                return self._async_get_entry()

        return self.async_show_form(
            step_id="user", data_schema=_schema(self._host, self._port), errors=errors
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host.rstrip(".")
        self._port = DEFAULT_PORT

        await self._set_unique_id_and_abort()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of a discovered player."""
        if user_input is not None:
            try:
                await validate_input(self.hass, self._host, self._port)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            return self._async_get_entry()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._host},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
