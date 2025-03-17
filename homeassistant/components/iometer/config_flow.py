"""Config flow for the IOmeter integration."""

from typing import Any, Final

from iometer import IOmeterClient, IOmeterConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

CONFIG_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})


class IOMeterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handles the config flow for a IOmeter bridge and core."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str
        self._meter_number: str

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: host})

        session = async_get_clientsession(self.hass)
        client = IOmeterClient(host=host, session=session)
        try:
            status = await client.get_current_status()
        except IOmeterConnectionError:
            return self.async_abort(reason="cannot_connect")

        self._meter_number = status.meter.number

        await self.async_set_unique_id(status.device.id)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": f"IOmeter {self._meter_number}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return await self._async_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"meter_number": self._meter_number},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = IOmeterClient(host=self._host, session=session)
            try:
                status = await client.get_current_status()
            except IOmeterConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self._meter_number = status.meter.number
                await self.async_set_unique_id(status.device.id)
                self._abort_if_unique_id_configured()
                return await self._async_create_entry()
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Create entry."""
        return self.async_create_entry(
            title=f"IOmeter {self._meter_number}",
            data={CONF_HOST: self._host},
        )
