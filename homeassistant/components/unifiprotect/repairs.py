"""unifiprotect.repairs."""

from __future__ import annotations

from typing import cast

from pyunifiprotect import ProtectApiClient
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry

from .const import CONF_ALLOW_EA
from .utils import async_create_api_client


class EAConfirm(RepairsFlow):
    """Handler for an issue fixing flow."""

    _api: ProtectApiClient
    _entry: ConfigEntry

    def __init__(self, api: ProtectApiClient, entry: ConfigEntry) -> None:
        """Create flow."""

        self._api = api
        self._entry = entry
        super().__init__()

    @callback
    def _async_get_placeholders(self) -> dict[str, str] | None:
        issue_registry = async_get_issue_registry(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return description_placeholders

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        nvr = await self._api.get_nvr()
        if await nvr.get_is_prerelease():
            return await self.async_step_confirm()
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            options = dict(self._entry.options)
            options[CONF_ALLOW_EA] = True
            self.hass.config_entries.async_update_entry(self._entry, options=options)
            return self.async_create_entry(title="", data={})

        placeholders = self._async_get_placeholders()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and issue_id == "ea_warning":
        entry_id = cast(str, data["entry_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            api = async_create_api_client(hass, entry)
            return EAConfirm(api, entry)
    return ConfirmRepairFlow()
