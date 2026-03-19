"""Config flow for WiiM integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from wiim.discovery import async_probe_wiim_device
from wiim.models import WiimProbeResult

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, LOGGER, UPNP_PORT

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _async_probe_wiim_host(hass: HomeAssistant, host: str) -> WiimProbeResult:
    """Probe the given host and return WiiM device information."""
    session = async_get_clientsession(hass)
    location = f"http://{host}:{UPNP_PORT}/description.xml"
    LOGGER.debug("Validating UPnP device at location: %s", location)
    try:
        probe_result = await async_probe_wiim_device(
            location,
            session,
            host=host,
        )
    except TimeoutError as err:
        raise CannotConnect from err

    if probe_result is None:
        raise CannotConnect
    return probe_result


class WiimConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiiM."""

    _discovered_info: WiimProbeResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when user adds integration manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                device_info = await _async_probe_wiim_host(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_info.udn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_info.name,
                    data={
                        CONF_HOST: device_info.host,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        LOGGER.debug(
            "Zeroconf discovery received: Name: %s, Host: %s, Port: %s, Properties: %s",
            discovery_info.name,
            discovery_info.host,
            discovery_info.port,
            discovery_info.properties,
        )

        host = discovery_info.host
        udn_from_txt = discovery_info.properties.get("uuid")
        if udn_from_txt:
            await self.async_set_unique_id(udn_from_txt)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            device_info = await _async_probe_wiim_host(self.hass, host)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device_info.udn)
        self._abort_if_unique_id_configured(updates={CONF_HOST: device_info.host})

        self._discovered_info = device_info
        self.context["title_placeholders"] = {"name": device_info.name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovered device."""
        discovered_info = self._discovered_info
        if user_input is not None and discovered_info is not None:
            return self.async_create_entry(
                title=discovered_info.name,
                data={
                    CONF_HOST: discovered_info.host,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": (
                    discovered_info.name
                    if discovered_info is not None
                    else "Discovered WiiM Device"
                )
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
