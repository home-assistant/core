"""Config flow for ZHA Infrared."""

from typing import Any, override

from homeassistant.components.zha.const import DOMAIN as ZHA_DOMAIN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN
from .helpers import get_supported_devices


class ZhaInfraredConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for ZHA Infrared."""

    VERSION = 1

    @override
    async def async_step_user(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if not self.hass.config_entries.async_entries(ZHA_DOMAIN):
            return self.async_abort(reason="no_zha")

        supported_devices = await self.hass.async_add_executor_job(
            get_supported_devices, self.hass
        )
        if not supported_devices:
            return self.async_abort(reason="no_supported_devices")

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="ZHA Infrared",
            data={},
        )
