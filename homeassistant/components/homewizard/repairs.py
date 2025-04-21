"""Repairs for HomeWizard integration."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .config_flow import async_request_token


class MigrateToV2ApiRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""

        if user_input is not None:
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="confirm", description_placeholders={"title": self.entry.title}
        )

    async def async_step_authorize(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the authorize step of a fix flow."""

        ip_address = self.entry.data[CONF_IP_ADDRESS]

        # Tell device we want a token, user must now press the button within 30 seconds
        # The first attempt will always fail, but this opens the window to press the button
        token = await async_request_token(self.hass, ip_address)
        errors: dict[str, str] | None = None

        if token is None:
            if user_input is not None:
                errors = {"base": "authorization_failed"}

            return self.async_show_form(step_id="authorize", errors=errors)

        data = {**self.entry.data, CONF_TOKEN: token}
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert data is not None
    assert isinstance(data["entry_id"], str)

    if issue_id.startswith("migrate_to_v2_api_") and (
        entry := hass.config_entries.async_get_entry(data["entry_id"])
    ):
        return MigrateToV2ApiRepairFlow(entry)

    raise ValueError(f"unknown repair {issue_id}")  # pragma: no cover
