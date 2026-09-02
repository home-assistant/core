"""Config flow for Wibeee energy monitor."""

from datetime import timedelta
import logging
from typing import Any, override

import aiohttp
from pywibeee import WibeeeAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_MAC_ADDRESS, CONF_WIBEEE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, data[CONF_HOST])

    try:
        device = await api.async_fetch_device_info()
    except (TimeoutError, aiohttp.ClientError) as exc:
        raise NoDeviceInfo(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": data[CONF_HOST], "error": str(exc)},
        ) from exc

    # The library returns None (instead of raising) when the MAC cannot be
    # determined; treat that as a connection failure for the user.
    if device is None:
        raise NoDeviceInfo(
            translation_domain=DOMAIN,
            translation_key="no_device_info",
            translation_placeholders={"host": data[CONF_HOST]},
        )

    return (
        f"Wibeee {device.mac_addr_short}",
        device.mac_addr_formatted,
        {
            CONF_HOST: data[CONF_HOST],
            CONF_MAC_ADDRESS: device.mac_addr_formatted,
            CONF_WIBEEE_ID: device.wibeee_id,
        },
    )


class WibeeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Wibeee config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of a Wibeee device."""
        host = discovery_info.ip
        mac = discovery_info.macaddress.replace(":", "").lower()

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        session = async_get_clientsession(self.hass)
        api = WibeeeAPI(session, host, timeout=timedelta(seconds=5))
        if not await api.async_check_connection():
            return self.async_abort(reason="not_wibeee_device")

        self._discovered_host = host
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of the discovered Wibeee device."""
        assert self._discovered_host is not None

        if user_input is not None:
            try:
                title, unique_id, data = await validate_input(
                    self.hass, {CONF_HOST: self._discovered_host}
                )
            except NoDeviceInfo:
                return self.async_abort(reason="cannot_connect")
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._discovered_host}
            )
            return self.async_create_entry(title=title, data=data)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._discovered_host},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step: enter the device IP address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                title, unique_id, data = await validate_input(self.hass, user_input)
            except NoDeviceInfo:
                errors[CONF_HOST] = "no_device_info"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=title, data=data)

        default_host = (user_input or {}).get(CONF_HOST, "")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=default_host): str}
            ),
            errors=errors,
        )


class NoDeviceInfo(HomeAssistantError):
    """Error to indicate we could not get info from a Wibeee device."""
