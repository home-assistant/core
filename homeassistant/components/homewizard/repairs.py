"""Repairs for HomeWizard integration."""

from homewizard_energy.errors import RequestError

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .config_flow import async_request_token
from .const import ISSUE_BATTERY_MODE_CLOUD_DISABLED


class MigrateToV2ApiRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""

        if user_input is not None:
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="confirm", description_placeholders={"title": self.entry.title}
        )

    async def async_step_authorize(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the authorize step of a fix flow."""

        ip_address = self.entry.data[CONF_IP_ADDRESS]

        # Tell device we want a token, user must now press the
        # button within 30 seconds. The first attempt will always
        # fail, but this opens the window to press the button.
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


class BatteryModeCloudDisabledRepairFlow(RepairsFlow):
    """Handler for a battery mode/cloud incompatibility fix flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            coordinator = self.entry.runtime_data
            try:
                await coordinator.api.system(cloud_enabled=True)
            except RequestError:
                errors = {"base": "network_error"}
            else:
                await coordinator.async_refresh()
                return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm", errors=errors)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is None or not isinstance(entry_id := data.get("entry_id"), str):
        return ConfirmRepairFlow()

    if issue_id.startswith("migrate_to_v2_api_") and (
        entry := hass.config_entries.async_get_entry(entry_id)
    ):
        return MigrateToV2ApiRepairFlow(entry)

    if issue_id.startswith(f"{ISSUE_BATTERY_MODE_CLOUD_DISABLED}_") and (
        entry := hass.config_entries.async_get_entry(entry_id)
    ):
        return BatteryModeCloudDisabledRepairFlow(entry)

    raise ValueError(f"unknown repair {issue_id}")  # pragma: no cover
