"""Config flow for the everHome integration."""

from typing import Any, Final, override

from ecotracker import EcoTracker
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

CONFIG_SCHEMA: Final = probatio.Schema({probatio.Required(CONF_HOST): str})


class EcoTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EcoTracker."""

    VERSION = 1

    _host: str
    _serial: str

    async def _async_get_serial(self, host: str) -> str | None:
        """Connect to the device and return its serial, or None if unreachable."""
        client = EcoTracker(host, port=80, session=async_get_clientsession(self.hass))
        if not await client.async_update():
            return None
        return client.get_data().serial

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if (serial := await self._async_get_serial(host)) is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial, raise_on_progress=False)
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

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        if not (serial := discovery_info.properties.get("serial")):
            return self.async_abort(reason="no_serial")
        self._serial = serial
        await self.async_set_unique_id(self._serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        if await self._async_get_serial(self._host) is None:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": f"EcoTracker {self._serial}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"EcoTracker {self._serial}",
                data={CONF_HOST: self._host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": "EcoTracker",
                "serial": self._serial,
                "host": self._host,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initiated by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if (serial := await self._async_get_serial(host)) is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )
