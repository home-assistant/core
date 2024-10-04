"""Config flow for EHEIM Digital."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from eheimdigital.hub import EheimDigitalHub
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST, default="eheimdigital"): selector.TextSelector()}
)


class EheimDigitalConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """The EHEIM Digital config flow."""

    data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host

        self._async_abort_entries_match(self.data)

        hub = EheimDigitalHub(
            session=async_create_clientsession(self.hass, base_url=f"http://{host}"),
            loop=self.hass.loop,
        )
        await hub.connect()
        await hub.update()
        await hub.close()
        await self.async_set_unique_id(hub.master.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data[CONF_HOST],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(step_id=SOURCE_USER, data_schema=CONFIG_SCHEMA)

        self._async_abort_entries_match(user_input)
        errors: dict[str, str] = {}
        hub = EheimDigitalHub(
            session=async_create_clientsession(
                self.hass, base_url=f"http://{user_input[CONF_HOST]}"
            ),
            loop=self.hass.loop,
        )

        try:
            await hub.connect()
            await hub.update()
            await hub.close()
        except ClientError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(hub.master.mac_address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(data=user_input, title=user_input[CONF_HOST])
        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )
