"""Config flow for the KEF integration."""

import logging
from typing import Any, override

import aiohttp
from pykefcontrol.kef_connector import KefAsyncConnector
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class KefConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEF."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            connector = KefAsyncConnector(host, session=session)

            try:
                mac = await connector.mac_address
                speaker_name = await connector.speaker_name
                speaker_model = await connector.get_speaker_model()
            except aiohttp.ClientError, TimeoutError, IndexError, KeyError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=speaker_name or "KEF Speaker",
                    data={CONF_HOST: host, "model": speaker_model},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
