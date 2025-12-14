"""Config flow for the Altruist integration."""

import logging
from typing import Any

from altruistclient import AltruistClient, AltruistDeviceModel, AltruistError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AltruistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Altruist."""

    device: AltruistDeviceModel

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        ip_address = ""
        if user_input is not None:
            ip_address = user_input[CONF_HOST]
            try:
                client = await AltruistClient.from_ip_address(
                    async_get_clientsession(self.hass), ip_address
                )
            except AltruistError:
                errors["base"] = "no_device_found"
            else:
                self.device = client.device
                await self.async_set_unique_id(
                    client.device_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self.device.id,
                    data={
                        CONF_HOST: ip_address,
                    },
                )

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_HOST): str}),
            {CONF_HOST: ip_address},
        )

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
        try:
            client = await AltruistClient.from_ip_address(
                async_get_clientsession(self.hass), str(discovery_info.ip_address)
            )
        except AltruistError:
            return self.async_abort(reason="no_device_found")

        self.device = client.device
        _LOGGER.debug("Zeroconf device: %s", client.device)
        await self.async_set_unique_id(client.device_id)
        self._abort_if_unique_id_configured()
        self.context.update(
            {
                "title_placeholders": {
                    "name": self.device.id,
                }
            }
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.device.id,
                data={
                    CONF_HOST: self.device.ip_address,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.device.id,
            },
        )
