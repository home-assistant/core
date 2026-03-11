"""Config flow to configure Motionblinds using their WLAN API."""

from __future__ import annotations

import logging
from typing import Any

from motionblinds import BlindType, MotionDiscovery, MotionGateway
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers import (
    device_registry,
    entity_registry,
    selector,
)

from .const import (
    CONF_BLIND_TYPE,
    CONF_COVER_DETAILS,
    CONF_INTERFACE,
    DEFAULT_BLIND_TYPE,
    CONF_WAIT_FOR_PUSH,
    DEFAULT_GATEWAY_NAME,
    DEFAULT_INTERFACE,
    DEFAULT_WAIT_FOR_PUSH,
    DOMAIN,
)
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
    }
)


class OptionsFlowHandler(OptionsFlowWithReload):
    """Options for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        if not hasattr(self, "_staged_options"):
            self._staged_options = self.config_entry.options.copy()

        errors: dict[str, str] = {}
        if user_input is not None:
            if CONF_COVER_DETAILS not in user_input:
                self._staged_options.update(user_input)
                return self.async_create_entry(title="", data=self._staged_options)

            selected_cover = user_input.pop(CONF_COVER_DETAILS)
            self._staged_options.update(user_input)
            return await self.async_show_details(selected_cover)

        settings_schema = vol.Schema(
            {
                vol.Optional(CONF_COVER_DETAILS): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(
                        entity=selector.EntityFilterSelectorConfig(
                            domain="cover",
                            integration=DOMAIN,
                        )
                    )
                ),
                vol.Optional(
                    CONF_WAIT_FOR_PUSH,
                    default=self._staged_options.get(
                        CONF_WAIT_FOR_PUSH, DEFAULT_WAIT_FOR_PUSH
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=settings_schema, errors=errors
        )

    async def async_show_details(self, selected_cover: str) -> ConfigFlowResult:
        dev_reg = device_registry.async_get(self.hass)
        device = dev_reg.async_get(selected_cover)
        if device is None:
            return await self.async_step_init()

        self._selected_cover_mac = next(
            (
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            ),
            None,
        )
        device_name = device.name_by_user or device.name_by_user or self._selected_cover_mac

        blind_type_key = f"{self._selected_cover_mac}_{CONF_BLIND_TYPE}"

        try:
            blind_type = BlindType(int(self._staged_options[blind_type_key]))
        except (KeyError, ValueError):
            blind_type = DEFAULT_BLIND_TYPE

        schema = {
            vol.Required(
                CONF_BLIND_TYPE, default=f"blind_type_{blind_type.name.lower()}"
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {
                            "value": f"blind_type_{v.name.lower()}",
                            "label": v.name,
                        }
                        for v in BlindType
                    ],
                    translation_key=CONF_BLIND_TYPE,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }

        return self.async_show_form(
            step_id="details",
            data_schema=vol.Schema(schema),
            errors={},
            description_placeholders={"device_name": device_name},
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        blind_type = DEFAULT_BLIND_TYPE

        if user_input:
            raw = user_input.get(CONF_BLIND_TYPE)
            if raw:
                prefix = "blind_type_"
                if raw.startswith(prefix):
                    name = raw[len(prefix):]
                    for v in BlindType:
                        if v.name.lower() == name:
                            blind_type = v
                            break

        blind_type_key = f"{self._selected_cover_mac}_{CONF_BLIND_TYPE}"

        if blind_type == DEFAULT_BLIND_TYPE:
            self._staged_options.pop(blind_type_key, None)
        else:
            self._staged_options[blind_type_key] = blind_type.value

        return await self.async_step_init()

class MotionBlindsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Motionblinds config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Motionblinds flow."""
        self._host: str | None = None
        self._ips: list[str] = []
        self._config_settings: vol.Schema | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        mac_address = format_mac(discovery_info.macaddress).replace(":", "")
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        gateway = MotionGateway(ip=discovery_info.ip, key="abcd1234-56ef-78")
        try:
            # key not needed for GetDeviceList request
            await self.hass.async_add_executor_job(gateway.GetDeviceList)
        except Exception:
            _LOGGER.exception("Failed to connect to Motion Gateway")
            return self.async_abort(reason="not_motionblinds")

        if not gateway.available:
            return self.async_abort(reason="not_motionblinds")

        short_mac = mac_address[-6:].upper()
        self.context["title_placeholders"] = {
            "short_mac": short_mac,
            "ip_address": discovery_info.ip,
        }

        self._host = discovery_info.ip
        return await self.async_step_connect()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._host = user_input.get(CONF_HOST)

            if self._host is not None:
                return await self.async_step_connect()

            # Use MotionGateway discovery
            discover_class = MotionDiscovery()
            gateways = await self.hass.async_add_executor_job(discover_class.discover)
            self._ips = list(gateways)

            if len(self._ips) == 1:
                self._host = self._ips[0]
                return await self.async_step_connect()

            if len(self._ips) > 1:
                return await self.async_step_select()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle multiple motion gateways found."""
        if user_input is not None:
            self._host = user_input["select_ip"]
            return await self.async_step_connect()

        select_schema = vol.Schema({vol.Required("select_ip"): vol.In(self._ips)})

        return self.async_show_form(step_id="select", data_schema=select_schema)

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect to the Motion Gateway."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY]
            assert self._host

            connect_gateway_class = ConnectMotionGateway(self.hass)
            if not await connect_gateway_class.async_connect_gateway(self._host, key):
                return self.async_abort(reason="connection_error")
            motion_gateway = connect_gateway_class.gateway_device

            # check socket interface
            check_multicast_class = ConnectMotionGateway(
                self.hass, interface=DEFAULT_INTERFACE
            )
            multicast_interface = await check_multicast_class.async_check_interface(
                self._host, key
            )

            mac_address = motion_gateway.mac

            await self.async_set_unique_id(mac_address, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self._host,
                    CONF_API_KEY: key,
                    CONF_INTERFACE: multicast_interface,
                }
            )

            return self.async_create_entry(
                title=DEFAULT_GATEWAY_NAME,
                data={
                    CONF_HOST: self._host,
                    CONF_API_KEY: key,
                    CONF_INTERFACE: multicast_interface,
                },
            )

        self._config_settings = vol.Schema(
            {
                vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
            }
        )

        return self.async_show_form(
            step_id="connect",
            data_schema=self._config_settings,
            errors=errors,
            description_placeholders={
                "documentation_url": "https://www.home-assistant.io/integrations/motion_blinds/#retrieving-the-api-key",
            },
        )
