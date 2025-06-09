"""Config flow for the Altruist integration."""

import ipaddress
import logging
from typing import Any

from altruistclient import AltruistClient, AltruistDeviceModel, AltruistError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_DEVICE_ID, CONF_IP_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AltruistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Altruist."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.device: AltruistDeviceModel | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        ip_address = ""
        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS]
            if self._is_valid_ip(ip_address):
                try:
                    client = await AltruistClient.from_ip_address(
                        async_get_clientsession(self.hass), ip_address
                    )
                except AltruistError:
                    errors["base"] = "no_device_found"
                else:
                    self.device = client.device
                    await self.async_set_unique_id(client.device_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Altruist {self.device.id}",
                        data={
                            CONF_IP_ADDRESS: ip_address,
                            CONF_DEVICE_ID: client.device_id,
                        },
                    )
            else:
                errors["base"] = "invalid_ip"

        data_schema = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "ip_address": ip_address,
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)
        client = await AltruistClient.from_ip_address(
            async_get_clientsession(self.hass), str(discovery_info.ip_address)
        )
        self.device = client.device
        _LOGGER.debug("Zeroconf device: %s", client.device)
        await self.async_set_unique_id(client.device_id)
        self._abort_if_unique_id_configured()
        self.context.update(
            {
                "title_placeholders": {
                    "name": f"Altruist {self.device.id}",
                }
            }
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.device
        if user_input is not None:
            return self.async_create_entry(
                title=f"Altruist {self.device.id}",
                data={
                    CONF_IP_ADDRESS: self.device.ip_address,
                    CONF_DEVICE_ID: self.device.id,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": f"Altruist {self.device.id}",
            },
        )

    def _is_valid_ip(self, ip_address: str) -> bool:
        """Validate the IP address."""
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            return False
        else:
            return True
