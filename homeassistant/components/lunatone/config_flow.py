"""Config flow for Lunatone."""

from typing import Any, Final

import aiohttp
from lunatone_rest_api_client import Auth, Info
from lunatone_rest_api_client.discovery import (
    LunatoneDiscoveryInfo,
    async_discover_devices,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA: Final[vol.Schema] = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)


def compose_title(name: str | None, serial_number: int) -> str:
    """Compose a title string from a given name and serial number."""
    return f"{name or 'DALI Gateway'} {serial_number}"


class LunatoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    _discovered_devices: list[LunatoneDiscoveryInfo] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._discovered_devices = await async_discover_devices(self.hass.loop)
        if not self._discovered_devices:
            return await self.async_step_url_input()
        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection."""
        if user_input is not None:
            selected_host = user_input[CONF_DEVICE]
            if selected_host == "__manual__":
                return await self.async_step_url_input()

            device = next(
                (d for d in self._discovered_devices if d.host == selected_host),
                None,
            )
            if device:
                return await self.async_step_url_input({"url": f"http://{device.host}"})

        device_options = {
            d.host: f"{d.name} ({d.host})" for d in self._discovered_devices
        }
        device_options["__manual__"] = "Enter URL manually"

        schema = vol.Schema({vol.Required("device"): vol.In(device_options)})
        return self.async_show_form(step_id="select_device", data_schema=schema)

    async def async_step_url_input(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the URL input."""
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
                if info_api.data is None or info_api.serial_number is None:
                    errors["base"] = "missing_device_info"
                else:
                    await self.async_set_unique_id(str(info_api.serial_number))
                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data_updates=data,
                            title=compose_title(info_api.name, info_api.serial_number),
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=compose_title(info_api.name, info_api.serial_number),
                        data={CONF_URL: url},
                    )
        return self.async_show_form(
            step_id="url_input",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_user(user_input)
