"""Config flow for Hot Spring."""

from typing import Any, override

from hotspring import HotSpring, HotSpringConnectionError, Spa
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN


class HotSpringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hot Spring."""

    VERSION = 1
    discovered_host: str
    discovered_spa: Spa

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                spa = await self._async_get_spa(user_input[CONF_HOST])
            except HotSpringConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    spa.info.mac_address, raise_on_progress=False
                )
                if self.source == SOURCE_RECONFIGURE:
                    entry = self._get_reconfigure_entry()
                    assert entry.unique_id is not None
                    self._abort_if_unique_id_mismatch(
                        reason="unique_id_mismatch",
                        description_placeholders={
                            "expected_mac": entry.unique_id.upper(),
                            "actual_mac": spa.info.mac_address.upper(),
                        },
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_HOST: user_input[CONF_HOST]},
                    )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=spa.info.hostname or "Hot Spring Spa",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        data_schema = vol.Schema({vol.Required(CONF_HOST): str})
        if self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self._get_reconfigure_entry().data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Hot Spring spa."""
        return await self.async_step_user(user_input)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        if mac := discovery_info.properties.get(CONF_MAC):
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.discovered_host = discovery_info.host
        try:
            self.discovered_spa = await self._async_get_spa(discovery_info.host)
        except HotSpringConnectionError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.discovered_spa.info.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        title = self.discovered_spa.info.hostname or "Hot Spring Spa"
        self.context.update(
            {
                "title_placeholders": {"name": title},
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        title = self.discovered_spa.info.hostname or "Hot Spring Spa"
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self.discovered_host,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": title},
        )

    async def _async_get_spa(self, host: str) -> Spa:
        """Get information from a Hot Spring spa."""
        api = HotSpring(host, session=async_get_clientsession(self.hass))
        return await api.update()
