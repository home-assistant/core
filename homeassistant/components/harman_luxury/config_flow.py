"""Config flow for the Harman Luxury integration."""

from typing import Any, override
from urllib.parse import urlparse

from aioharmanluxury import DeviceInfo, HarmanLuxuryClient, HarmanLuxuryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_SERIAL, SsdpServiceInfo

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class HarmanLuxuryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Harman Luxury."""

    _host: str
    _name: str

    async def _async_get_info(self, host: str) -> DeviceInfo | None:
        """Return the device info, or ``None`` if it has no usable identity."""
        client = HarmanLuxuryClient(host, async_get_clientsession(self.hass))
        try:
            info = await client.async_get_info()
        except HarmanLuxuryError:
            return None
        if not info.serial:
            return None
        return info

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self._async_get_info(user_input[CONF_HOST])
            if info is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by SSDP discovery."""
        host = urlparse(discovery_info.ssdp_location or "").hostname
        serial = discovery_info.upnp.get(ATTR_UPNP_SERIAL)
        if not host or not serial:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        info = await self._async_get_info(host)
        # The unique ID is the advertised serial; refuse a device whose API
        # reports a different one, so setup cannot later fail on the mismatch.
        if info is None or info.serial != serial:
            return self.async_abort(reason="cannot_connect")

        self._host = host
        self._name = info.name
        self.context["title_placeholders"] = {"name": info.name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name, data={CONF_HOST: self._host}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._name},
        )
