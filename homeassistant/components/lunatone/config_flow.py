"""Config flow for Lunatone."""

import logging
from typing import Any, Final

import aiohttp
from lunatone_rest_api_client import Auth, Info
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA: Final[vol.Schema] = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)


class LunatoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._name: str | None = None
        self._serial_number: int | None = None

    @property
    def _title(self) -> str:
        return f"{self._name or 'DALI Gateway'} {self._serial_number}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            data = {CONF_URL: url}
            self._async_abort_entries_match(data)
            auth = Auth(
                session=async_get_clientsession(self.hass),
                base_url=url,
            )
            info = Info(auth)
            try:
                await info.async_update()
            except aiohttp.InvalidUrlClientError:
                errors["base"] = "invalid_url"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if info.data is None or info.serial_number is None:
                    errors["base"] = "missing_device_info"
                else:
                    self._name = info.name
                    self._serial_number = info.serial_number
                    await self.async_set_unique_id(str(self._serial_number))
                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data_updates=data,
                            title=self._title,
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=self._title,
                        data={CONF_URL: url},
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_user(user_input)
