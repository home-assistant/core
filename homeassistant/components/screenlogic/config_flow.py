"""Config flow for ScreenLogic."""
from __future__ import annotations

import logging

from screenlogicpy import ScreenLogicError, discovery
from screenlogicpy.const import SL_GATEWAY_IP, SL_GATEWAY_NAME, SL_GATEWAY_PORT
from screenlogicpy.requests import login
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

GATEWAY_SELECT_KEY = "selected_gateway"
GATEWAY_MANUAL_ENTRY = "manual"

PENTAIR_OUI = "00-C0-33"


async def async_discover_gateways_by_unique_id(hass):
    """Discover gateways and return a dict of them by unique id."""
    discovered_gateways = {}
    try:
        hosts = await discovery.async_discover()
        _LOGGER.debug("Discovered hosts: %s", hosts)
    except ScreenLogicError as ex:
        _LOGGER.debug(ex)
        return discovered_gateways

    for host in hosts:
        if (name := host[SL_GATEWAY_NAME]).startswith("Pentair:"):
            mac = _extract_mac_from_name(name)
            discovered_gateways[mac] = host

    _LOGGER.debug("Discovered gateways: %s", discovered_gateways)
    return discovered_gateways


def _extract_mac_from_name(name):
    return format_mac(f"{PENTAIR_OUI}-{name.split(':')[1].strip()}")


def short_mac(mac):
    """Short version of the mac as seen in the app."""
    return "-".join(mac.split(":")[3:]).upper()


def name_for_mac(mac):
    """Derive the gateway name from the mac."""
    return f"Pentair: {short_mac(mac)}"


class ScreenlogicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow to setup screen logic devices."""

    VERSION = 1

    def __init__(self):
        """Initialize ScreenLogic ConfigFlow."""
        self.discovered_gateways = {}
        self.discovered_ip = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ScreenLogicOptionsFlowHandler:
        """Get the options flow for ScreenLogic."""
        return ScreenLogicOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        self.discovered_gateways = await async_discover_gateways_by_unique_id(self.hass)
        return await self.async_step_gateway_select()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        mac = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.ip}
        )
        self.discovered_ip = discovery_info.ip
        self.context["title_placeholders"] = {"name": discovery_info.hostname}
        return await self.async_step_gateway_entry()

    async def async_step_gateway_select(self, user_input=None):
        """Handle the selection of a discovered ScreenLogic gateway."""
        existing = self._async_current_ids()
        unconfigured_gateways = {
            mac: gateway[SL_GATEWAY_NAME]
            for mac, gateway in self.discovered_gateways.items()
            if mac not in existing
        }

        if not unconfigured_gateways:
            return await self.async_step_gateway_entry()

        errors = {}
        if user_input is not None:
            if user_input[GATEWAY_SELECT_KEY] == GATEWAY_MANUAL_ENTRY:
                return await self.async_step_gateway_entry()

            mac = user_input[GATEWAY_SELECT_KEY]
            selected_gateway = self.discovered_gateways[mac]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name_for_mac(mac),
                data={
                    CONF_IP_ADDRESS: selected_gateway[SL_GATEWAY_IP],
                    CONF_PORT: selected_gateway[SL_GATEWAY_PORT],
                },
            )

        return self.async_show_form(
            step_id="gateway_select",
            data_schema=vol.Schema(
                {
                    vol.Required(GATEWAY_SELECT_KEY): vol.In(
                        {
                            **unconfigured_gateways,
                            GATEWAY_MANUAL_ENTRY: "Manually configure a ScreenLogic gateway",
                        }
                    )
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_gateway_entry(self, user_input=None):
        """Handle the manual entry of a ScreenLogic gateway."""
        errors = {}
        ip_address = self.discovered_ip
        port = 80

        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS]
            port = user_input[CONF_PORT]
            try:
                mac = format_mac(await login.async_get_mac_address(ip_address, port))
            except ScreenLogicError as ex:
                _LOGGER.debug(ex)
                errors[CONF_IP_ADDRESS] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(mac, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name_for_mac(mac),
                    data={
                        CONF_IP_ADDRESS: ip_address,
                        CONF_PORT: port,
                    },
                )

        return self.async_show_form(
            step_id="gateway_entry",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS, default=ip_address): str,
                    vol.Required(CONF_PORT, default=port): int,
                }
            ),
            errors=errors,
            description_placeholders={},
        )


class ScreenLogicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options for the ScreenLogic integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init the screen logic options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL))
                }
            ),
            description_placeholders={"gateway_name": self.config_entry.title},
        )
