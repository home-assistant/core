"""Config flow for Hunter Douglas PowerView integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub
import voluptuous as vol

from homeassistant.components import dhcp, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import async_get_device_info
from .const import DOMAIN, HUB_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

HAP_SUFFIX = "._hap._tcp.local."
POWERVIEW_G2_SUFFIX = "._powerview._tcp.local."
POWERVIEW_G3_SUFFIX = "._powerview-g3._tcp.local."


async def validate_input(hass: HomeAssistant, hub_address: str) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    websession = async_get_clientsession(hass)

    pv_request = AioRequest(hub_address, loop=hass.loop, websession=websession)

    try:
        hub = Hub(pv_request)
        await hub.query_firmware()
        device_info = await async_get_device_info(hub)
    except HUB_EXCEPTIONS as err:
        raise CannotConnect from err

    if hub.role != "Primary":
        raise UnsupportedDevice(
            f"{hub.name} ({hub.hub_address}) is the {hub.role} Hub. "
            "Only the Primary can manage shades"
        )

    _LOGGER.debug("Connection made using api version: %s", hub.api_version)

    # Return info that you want to store in the config entry.
    return {
        "title": device_info.name,
        "unique_id": device_info.serial_number,
        CONF_API_VERSION: hub.api_version,
    }


class PowerviewConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hunter Douglas PowerView."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the powerview config flow."""
        self.powerview_config: dict = {}
        self.discovered_ip: str | None = None
        self.discovered_name: str | None = None
        self.data_schema: dict = {vol.Required(CONF_HOST): str}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            info, error = await self._async_validate_or_error(user_input[CONF_HOST])

            if info and not error:
                self.powerview_config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_NAME: info["title"],
                    CONF_API_VERSION: info[CONF_API_VERSION],
                }
                await self.async_set_unique_id(info["unique_id"])
                return self.async_create_entry(
                    title=self.powerview_config[CONF_NAME],
                    data={
                        CONF_HOST: self.powerview_config[CONF_HOST],
                        CONF_API_VERSION: self.powerview_config[CONF_API_VERSION],
                    },
                )

            if TYPE_CHECKING:
                assert error is not None
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self.data_schema), errors=errors
        )

    async def _async_validate_or_error(
        self, host: str
    ) -> tuple[dict[str, str], None] | tuple[None, str]:
        self._async_abort_entries_match({CONF_HOST: host})

        try:
            info = await validate_input(self.hass, host)
        except CannotConnect:
            return None, "cannot_connect"
        except UnsupportedDevice:
            return None, "unsupported_device"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, "unknown"

        return info, None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        self.discovered_ip = discovery_info.ip
        self.discovered_name = discovery_info.hostname
        return await self.async_step_discovery_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.discovered_ip = discovery_info.host
        name = discovery_info.name.removesuffix(POWERVIEW_G2_SUFFIX)
        name = name.removesuffix(POWERVIEW_G3_SUFFIX)
        self.discovered_name = name
        return await self.async_step_discovery_confirm()

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        self.discovered_ip = discovery_info.host
        name = discovery_info.name.removesuffix(HAP_SUFFIX)
        self.discovered_name = name
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self) -> ConfigFlowResult:
        """Confirm dhcp or homekit discovery."""
        # If we already have the host configured do
        # not open connections to it if we can avoid it.
        assert self.discovered_ip and self.discovered_name is not None
        self.context[CONF_HOST] = self.discovered_ip
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self.discovered_ip:
                return self.async_abort(reason="already_in_progress")

        self._async_abort_entries_match({CONF_HOST: self.discovered_ip})
        info, error = await self._async_validate_or_error(self.discovered_ip)
        if error:
            return self.async_abort(reason=error)
        assert info is not None

        api_version = info[CONF_API_VERSION]
        if not self.discovered_name:
            self.discovered_name = f"Powerview Generation {api_version}"

        await self.async_set_unique_id(info["unique_id"], raise_on_progress=False)
        self._abort_if_unique_id_configured({CONF_HOST: self.discovered_ip})

        self.powerview_config = {
            CONF_HOST: self.discovered_ip,
            CONF_NAME: self.discovered_name,
            CONF_API_VERSION: api_version,
        }
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with Powerview."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.powerview_config[CONF_NAME],
                data={
                    CONF_HOST: self.powerview_config[CONF_HOST],
                    CONF_API_VERSION: self.powerview_config[CONF_API_VERSION],
                },
            )

        self._set_confirm_only()
        self.context["title_placeholders"] = self.powerview_config
        return self.async_show_form(
            step_id="link", description_placeholders=self.powerview_config
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class UnsupportedDevice(HomeAssistantError):
    """Error to indicate the device is not supported."""
