"""Repairs platform for Shelly integration."""

from __future__ import annotations

from typing import cast

from aiohttp import BasicAuth
from aioshelly.common import trigger_ota_http
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class FirmwareUpdateFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, host: str, gen: int, auth: BasicAuth) -> None:
        """Init FirmwareUpdateFlow."""
        self._host = host
        self._gen = gen
        self._auth = auth
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""

        if user_input is not None:
            return await self.async_update_firmware()

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))

    async def async_update_firmware(self) -> data_entry_flow.FlowResult:
        """Update firmware."""

        aiohttp_session = async_get_clientsession(self.hass)
        update = await trigger_ota_http(
            aiohttp_session, self._host, self._gen, self._auth
        )
        if update:
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="update_failed",
            data_schema=vol.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and "firmware_unsupported" in issue_id:
        host = cast(str, data["host"])
        gen = int(cast(str, data["gen"]))
        username = cast(str, data["username"])
        password = cast(str, data["password"])
        auth = BasicAuth(username, password)
        return FirmwareUpdateFlow(host, gen, auth)

    return ConfirmRepairFlow()
