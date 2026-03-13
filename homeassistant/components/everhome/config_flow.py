"""Config flow for the everHome integration."""

from typing import Any, Final

from ecotracker import EcoTracker
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

CONFIG_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})


class EcoTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EcoTracker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _host: str
    _serial: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = EcoTracker(host, session=session)
            if not await client.async_update():
                errors["base"] = "cannot_connect"
            else:
                serial = client.get_data().serial
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"EcoTracker {serial}",
                    data={CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery Todo add check."""
        self._host = discovery_info.host
        self._serial = discovery_info.properties["serial"]
        await self.async_set_unique_id(self._serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        session = async_get_clientsession(self.hass)
        client = EcoTracker(self._host, session=session)
        if not await client.async_update():
            return self.async_abort(reason="cannot_connect")

        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": f"EcoTracker {self._serial}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"EcoTracker {self._serial}",
                data={CONF_HOST: self._host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"serial": self._serial},
        )
