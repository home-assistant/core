"""Config flow for Hot Spring."""

from collections.abc import Mapping
from typing import Any, override

from hotspring import HotSpring, HotSpringConnectionError, HotSpringError, Spa
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> Spa:
    """Validate the user input allows us to connect."""
    api = HotSpring(data[CONF_HOST], session=async_get_clientsession(hass))
    spa = await api.update()
    if not spa.info.mac_address:
        raise HotSpringError("No MAC address found")
    return spa


class HotSpringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hot Spring."""

    VERSION = 1
    discovered_host: str
    discovered_spa: Spa
    discovered_title: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                spa = await validate_input(self.hass, user_input)
            except HotSpringConnectionError, HotSpringError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(spa.info.mac_address)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
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

        suggested_values: Mapping[str, Any] | None = user_input
        if suggested_values is None and self.source == SOURCE_RECONFIGURE:
            suggested_values = self._get_reconfigure_entry().data

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                suggested_values,
            ),
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
        self.discovered_host = discovery_info.host
        try:
            self.discovered_spa = await validate_input(
                self.hass, {CONF_HOST: discovery_info.host}
            )
        except HotSpringConnectionError, HotSpringError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.discovered_spa.info.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.discovered_title = self.discovered_spa.info.hostname or "Hot Spring Spa"
        self.context["title_placeholders"] = {"name": self.discovered_title}

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.discovered_title},
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        return self.async_create_entry(
            title=self.discovered_title,
            data={CONF_HOST: self.discovered_host},
        )
