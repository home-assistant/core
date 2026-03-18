"""Config flow for Droplet integration."""

from __future__ import annotations

from typing import Any

from pydroplet.droplet import DropletConnection, DropletDiscovery
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_DEVICE_ID, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN


def normalize_pairing_code(code: str) -> str:
    """Normalize pairing code by removing spaces and capitalizing."""
    return code.replace(" ", "").upper()


class DropletConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Droplet config flow."""

    _droplet_discovery: DropletDiscovery

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._droplet_discovery = DropletDiscovery(
            discovery_info.host,
            discovery_info.port,
            discovery_info.name,
        )
        if not self._droplet_discovery.is_valid():
            return self.async_abort(reason="invalid_discovery_info")

        # In this case, device ID was part of the zeroconf discovery info
        device_id: str = await self._droplet_discovery.get_device_id()
        await self.async_set_unique_id(device_id)

        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: self._droplet_discovery.host},
        )

        self.context.update({"title_placeholders": {"name": device_id}})
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        errors: dict[str, str] = {}
        device_id: str = await self._droplet_discovery.get_device_id()
        if user_input is not None:
            # Test if we can connect before returning
            session = async_get_clientsession(self.hass)
            code = normalize_pairing_code(user_input[CONF_CODE])
            if await self._droplet_discovery.try_connect(session, code):
                device_data = {
                    CONF_IP_ADDRESS: self._droplet_discovery.host,
                    CONF_PORT: self._droplet_discovery.port,
                    CONF_DEVICE_ID: device_id,
                    CONF_CODE: code,
                }

                return self.async_create_entry(
                    title=device_id,
                    data=device_data,
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): str,
                }
            ),
            description_placeholders={
                "device_name": device_id,
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._droplet_discovery = DropletDiscovery(
                user_input[CONF_IP_ADDRESS], DropletConnection.DEFAULT_PORT, ""
            )
            session = async_get_clientsession(self.hass)
            code = normalize_pairing_code(user_input[CONF_CODE])
            if await self._droplet_discovery.try_connect(session, code) and (
                device_id := await self._droplet_discovery.get_device_id()
            ):
                device_data = {
                    CONF_IP_ADDRESS: self._droplet_discovery.host,
                    CONF_PORT: self._droplet_discovery.port,
                    CONF_DEVICE_ID: device_id,
                    CONF_CODE: code,
                }
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    description_placeholders={CONF_DEVICE_ID: device_id},
                )

                return self.async_create_entry(
                    title=device_id,
                    data=device_data,
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_IP_ADDRESS): str, vol.Required(CONF_CODE): str}
            ),
            errors=errors,
        )
