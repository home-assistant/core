"""Config flow for ScreenLogic."""

import logging
from typing import Any

from screenlogicpy import ScreenLogicError, ScreenLogicGateway, discovery
from screenlogicpy.const.common import SL_GATEWAY_IP, SL_GATEWAY_NAME, SL_GATEWAY_PORT
from screenlogicpy.requests import async_resolve_remote_gateway, login
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_ADAPTER_ID,
    CONF_CONNECTION_TYPE,
    CONF_SYSTEM_NAME,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

GATEWAY_SELECT_KEY = "selected_gateway"
GATEWAY_MANUAL_ENTRY = "manual"

PENTAIR_OUI = "00-C0-33"


async def async_discover_gateways_by_unique_id() -> dict[str, dict[str, Any]]:
    """Discover gateways and return a dict of them by unique id."""
    discovered_gateways: dict[str, dict[str, Any]] = {}
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



def normalize_adapter_id(adapter_id: str) -> str:
    """Normalize a ScreenLogic adapter ID to XX-XX-XX."""
    value = adapter_id.strip().upper()
    value = value.replace("PENTAIR:", "").strip()
    value = value.replace(":", "-")
    value = "".join(char for char in value if char in "0123456789ABCDEF")

    if len(value) != 6:
        raise ValueError("adapter_id must contain exactly six hex characters")

    return "-".join(value[i : i + 2] for i in range(0, 6, 2))


def system_name_for_adapter_id(adapter_id: str) -> str:
    """Return Pentair remote system name for adapter ID."""
    return f"Pentair: {normalize_adapter_id(adapter_id)}"


async def async_validate_remote_gateway(
    adapter_id: str, password: str
) -> dict[str, str]:
    """Resolve and validate a remote ScreenLogic gateway."""
    normalized_adapter_id = normalize_adapter_id(adapter_id)
    system_name = system_name_for_adapter_id(normalized_adapter_id)

    remote = await async_resolve_remote_gateway(system_name)
    if not remote.gateway_found or not remote.license_ok or not remote.ip_addr:
        raise ScreenLogicError("Remote ScreenLogic gateway was not found")

    gateway = ScreenLogicGateway()
    try:
        if not await gateway.async_connect(
            ip=remote.ip_addr,
            port=remote.port,
            name=system_name,
            password=password,
            remote=True,
        ):
            raise ScreenLogicError("Remote ScreenLogic login failed")

        return {
            CONF_ADAPTER_ID: normalized_adapter_id,
            CONF_SYSTEM_NAME: system_name,
            "unique_id": format_mac(gateway.mac),
        }
    finally:
        if gateway.is_connected:
            await gateway.async_disconnect(force=True)

def _extract_mac_from_name(name: str) -> str:
    return format_mac(f"{PENTAIR_OUI}-{name.split(':')[1].strip()}")


def short_mac(mac: str) -> str:
    """Short version of the mac as seen in the app."""
    return "-".join(mac.split(":")[3:]).upper()


def name_for_mac(mac: str) -> str:
    """Derive the gateway name from the mac."""
    return f"Pentair: {short_mac(mac)}"


class ScreenlogicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow to setup screen logic devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize ScreenLogic ConfigFlow."""
        self.discovered_gateways: dict[str, dict[str, Any]] = {}
        self.discovered_ip: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ScreenLogicOptionsFlowHandler:
        """Get the options flow for ScreenLogic."""
        return ScreenLogicOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if user_input is not None:
            if user_input[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_REMOTE:
                return await self.async_step_remote_entry()

            self.discovered_gateways = await async_discover_gateways_by_unique_id()
            return await self.async_step_gateway_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONNECTION_TYPE,
                        default=CONNECTION_TYPE_LOCAL,
                    ): vol.In(
                        {
                            CONNECTION_TYPE_LOCAL: "Local network",
                            CONNECTION_TYPE_REMOTE: "Remote access",
                        }
                    )
                }
            ),
            errors={},
            description_placeholders={},
        )

    async def async_step_remote_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle remote ScreenLogic setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validation = await async_validate_remote_gateway(
                    user_input[CONF_ADAPTER_ID],
                    user_input[CONF_PASSWORD],
                )
            except (ScreenLogicError, ValueError) as ex:
                _LOGGER.debug("Remote ScreenLogic setup failed: %s", ex)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    validation["unique_id"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=validation[CONF_SYSTEM_NAME],
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
                        CONF_ADAPTER_ID: validation[CONF_ADAPTER_ID],
                        CONF_SYSTEM_NAME: validation[CONF_SYSTEM_NAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="remote_entry",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADAPTER_ID): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        mac = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.ip}
        )
        self.discovered_ip = discovery_info.ip
        self.context["title_placeholders"] = {"name": discovery_info.hostname}
        return await self.async_step_gateway_entry()

    async def async_step_gateway_select(self, user_input=None) -> ConfigFlowResult:
        """Handle the selection of a discovered ScreenLogic gateway."""
        existing = self._async_current_ids(include_ignore=False)
        unconfigured_gateways = {
            mac: gateway[SL_GATEWAY_NAME]
            for mac, gateway in self.discovered_gateways.items()
            if mac not in existing
        }

        if not unconfigured_gateways:
            return await self.async_step_gateway_entry()

        errors: dict[str, str] = {}
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
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
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
                            GATEWAY_MANUAL_ENTRY: (
                                "Manually configure a ScreenLogic gateway"
                            ),
                        }
                    )
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_gateway_entry(self, user_input=None) -> ConfigFlowResult:
        """Handle the manual entry of a ScreenLogic gateway."""
        errors: dict[str, str] = {}
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
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
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


class ScreenLogicOptionsFlowHandler(OptionsFlow):
    """Handles the options for the ScreenLogic integration."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
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
                    # Polling interval is user-configurable, which is no longer allowed
                    # pylint: disable-next=hass-config-flow-polling-field
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL))
                }
            ),
            description_placeholders={"gateway_name": self.config_entry.title},
        )
