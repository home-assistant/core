"""Config flow for Starlink."""

from __future__ import annotations

from typing import Any

from starlink_grpc import ChannelContext, GrpcError, get_id
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_IP_ADDRESS, default="192.168.100.1:9200"): str}
)


class StarlinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """The configuration flow for a Starlink system."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a server address and a name for the system."""
        errors = {}
        if user_input:
            # Input validation. If everything looks good, create the entry
            if uid := await self.get_device_id(url=user_input[CONF_IP_ADDRESS]):
                # Make sure we're not configuring the same device
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Starlink",
                    data=user_input,
                )
            errors[CONF_IP_ADDRESS] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def get_device_id(self, url: str) -> str | None:
        """Get the device UID, or None if no device exists at the given URL."""
        context = ChannelContext(target=url)
        response: str | None
        try:
            response = await self.hass.async_add_executor_job(get_id, context)
        except GrpcError:
            response = None
        context.close()
        return response
