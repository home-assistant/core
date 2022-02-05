"""Config flow to configure the Cybro PLC integration."""
from __future__ import annotations

from typing import Any

from cybro import Cybro, CybroConnectionError, Device
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# from homeassistant.components import zeroconf
from . import PLATFORM_NAMES, binary_sensor
from .const import DOMAIN, LOGGER
from .coordinator import CybroDataUpdateCoordinator


class CybroFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Cybro PLC config flow."""

    VERSION = 1
    discovered_host: str
    discovered_device: Device

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CybroOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CybroOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                device = await self._async_get_device(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_ADDRESS],
                )
            except CybroConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if device.server_info.scgi_port_status == "":
                    return self.async_abort(reason="scgi_server_not_running")
                if device.plc_info.plc_program_status != "ok":
                    return self.async_abort(reason="plc_not_existing")
                title_name = f"c{user_input[CONF_ADDRESS]}@{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title_name,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_ADDRESS: user_input[CONF_ADDRESS],
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="127.0.0.1"): str,
                    vol.Required(CONF_PORT, default=4000): int,
                    vol.Required(CONF_ADDRESS, default=1000): int,
                }
            ),
            errors=errors or {},
        )

    #    async def async_step_zeroconf(
    #        self, discovery_info: zeroconf.ZeroconfServiceInfo
    #    ) -> FlowResult:
    #        """Handle zeroconf discovery."""
    #        # Abort quick if the mac address is provided by discovery info
    #        # if mac := discovery_info.properties.get(CONF_MAC):
    #        #    await self.async_set_unique_id(mac)
    #        #    self._abort_if_unique_id_configured(
    #        #        updates={CONF_HOST: discovery_info.host}
    #        #    )
    #
    #        self.discovered_host = discovery_info.host
    #        try:
    #            self.discovered_device = await self._async_get_device(
    #                discovery_info.host, discovery_info.port, 1234
    #            )
    #        except CybroConnectionError:
    #            return self.async_abort(reason="cannot_connect")
    #
    #        await self.async_set_unique_id(self.discovered_device.info.mac_address)
    #        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
    #
    #        self.context.update(
    #            {
    #                "title_placeholders": {"name": self.discovered_device.info.name},
    #                "configuration_url": f"http://{discovery_info.host}",
    #            }
    #        )
    #        return await self.async_step_zeroconf_confirm()
    #
    #    async def async_step_zeroconf_confirm(
    #        self, user_input: dict[str, Any] | None = None
    #    ) -> FlowResult:
    #        """Handle a flow initiated by zeroconf."""
    #        if user_input is not None:
    #            return self.async_create_entry(
    #                title=self.discovered_device.info.name,
    #                data={CONF_HOST: self.discovered_host},
    #            )
    #
    #        return self.async_show_form(
    #            step_id="zeroconf_confirm",
    #            description_placeholders={"name": self.discovered_device.info.name},
    #        )
    #
    async def _async_get_device(self, host: str, port: int, address: int) -> Device:
        """Get device information from Cybro device."""
        session = async_get_clientsession(self.hass)
        cybro = Cybro(host, port=port, session=session, nad=address)
        return await cybro.update(plc_nad=address)


class CybroOptionsFlowHandler(OptionsFlow):
    """Handle Cybro options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Cybro options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Cybro options."""
        coordinator: CybroDataUpdateCoordinator = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]
        if user_input is not None:
            if user_input[CONF_PLATFORM] == "binary_sensor":
                await binary_sensor.async_setup_entry(
                    hass=self.hass,
                    entry=self.config_entry,
                    async_add_entities=binary_sensor.CybroUpdateBinarySensor,
                    variable_name=user_input[CONF_UNIQUE_ID],
                )
            # return self.async_create_entry(title="", data={})
            LOGGER.debug(user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UNIQUE_ID, default=f"c{coordinator.cybro.nad}.cybro_ix00"
                    ): str,
                    vol.Required(CONF_PLATFORM): vol.In(PLATFORM_NAMES),
                }
            ),
        )
