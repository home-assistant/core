"""Config flow for Lunatone."""

from typing import Any, Final

import aiohttp
from lunatone_rest_api_client import Auth, Info
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

DATA_SCHEMA: Final[vol.Schema] = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)


class LunatoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            data = {CONF_URL: url}
            self._async_abort_entries_match(data)
            auth_api = Auth(
                session=async_get_clientsession(self.hass),
                base_url=url,
            )
            info_api = Info(auth_api)
            try:
                await info_api.async_update()
            except aiohttp.InvalidUrlClientError:
                errors["base"] = "invalid_url"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if info_api.serial_number is None:
                    errors["base"] = "missing_device_info"
                else:
                    unique_id = str(info_api.serial_number)
                    if info_api.uid is not None:
                        unique_id = info_api.uid.replace("-", "")
                    await self.async_set_unique_id(unique_id)
                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(), data_updates=data, title=url
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=url, data=data)
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        url = URL.build(scheme="http", host=discovery_info.host)
        uid = discovery_info.properties["uid"]
        await self.async_set_unique_id(uid.replace("-", ""))
        self._abort_if_unique_id_configured(updates={CONF_URL: url.human_repr()})

        self._data[CONF_URL] = url.human_repr()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device."""
        data = {CONF_URL: self._data[CONF_URL]}
        if user_input is not None:
            return await self.async_step_user(data)
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if user_input is not None:
            return await self.async_step_user(user_input)

        entry = self._get_reconfigure_entry()
        suggested_values = {CONF_URL: entry.data[CONF_URL]}

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_URL): cv.string}), suggested_values
            ),
        )
