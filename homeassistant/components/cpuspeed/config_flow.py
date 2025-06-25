"""Config flow to configure the CPU Speed integration."""

from __future__ import annotations

from typing import Any

from cpuinfo import cpuinfo

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class CPUSpeedFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for CPU Speed."""

    VERSION = 1

    _imported_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)

        if user_input is None:
            return self.async_show_form(step_id="user")

        if not await self.hass.async_add_executor_job(cpuinfo.get_cpu_info):
            return self.async_abort(reason="not_compatible")

        return self.async_create_entry(
            title=self._imported_name or "CPU Speed",
            data={},
        )
