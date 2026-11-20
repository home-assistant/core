"""Repairs for HomeWizard integration."""

import asyncio
from typing import override

from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback

from .config_flow import async_wait_for_token
from .const import ISSUE_BATTERY_MODE_CLOUD_DISABLED, LOGGER
from .coordinator import HomeWizardConfigEntry

IDENTIFY_INTERVAL = 2
IDENTIFY_DURATION = 300


class MigrateToV2ApiRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _identify_task: asyncio.Task[None] | None = None
    _token: str | None = None
    _token_task: asyncio.Task[str] | None = None

    def __init__(self, entry: HomeWizardConfigEntry) -> None:
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

        placeholders = {"title": self.entry.title}
        if not self._can_identify():
            return self.async_show_form(
                step_id="confirm", description_placeholders=placeholders
            )

        if self._identify_task is None:
            self._async_start_identify()
        return self.async_show_form(
            step_id="confirm_identify", description_placeholders=placeholders
        )

    async def async_step_confirm_identify(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step while the device is identifying itself."""
        return await self.async_step_confirm(user_input)

    def _can_identify(self) -> bool:
        return (
            self.entry.state is ConfigEntryState.LOADED
            and self.entry.runtime_data.data.device.supports_identify()
        )

    @callback
    @override
    def async_remove(self) -> None:
        """Stop identifying the device when the flow is closed."""
        self._async_stop_identify()

    @callback
    def _async_start_identify(self) -> None:
        self._identify_task = self.entry.async_create_background_task(
            self.hass,
            self._async_identify_device(),
            f"homewizard identify {self.entry.entry_id}",
        )

    @callback
    def _async_stop_identify(self) -> None:
        if self._identify_task is not None:
            self._identify_task.cancel()
            self._identify_task = None

    async def _async_identify_device(self) -> None:
        """Keep blinking the status light so the user can find the device."""
        coordinator = self.entry.runtime_data
        try:
            async with asyncio.timeout(IDENTIFY_DURATION):
                while True:
                    await coordinator.api.identify()
                    await asyncio.sleep(IDENTIFY_INTERVAL)
        except TimeoutError:
            pass
        except DisabledError, RequestError, UnsupportedError:
            LOGGER.debug("Could not identify %s", self.entry.title)

    async def async_step_authorize(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Wait in the background until the user presses the device button."""
        if self._token_task is None:
            # Restart identifying so it lasts as long as the token polling
            self._async_stop_identify()
            if self._can_identify():
                self._async_start_identify()
            self._token_task = self.hass.async_create_task(
                async_wait_for_token(self.hass, self.entry.data[CONF_IP_ADDRESS])
            )

        if not self._token_task.done():
            return self.async_show_progress(
                step_id="authorize",
                progress_action="wait_for_button",
                progress_task=self._token_task,
            )

        self._async_stop_identify()
        token_task, self._token_task = self._token_task, None
        try:
            self._token = token_task.result()
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="authorize_timeout")
        return self.async_show_progress_done(next_step_id="finish_authorize")

    async def async_step_authorize_timeout(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Let the user retry after the button was not pressed in time."""
        if user_input is not None:
            return await self.async_step_authorize()
        return self.async_show_form(step_id="authorize_timeout")

    async def async_step_finish_authorize(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Store the received token and reload the entry."""
        data = {**self.entry.data, CONF_TOKEN: self._token}
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return self.async_create_entry(data={})


class BatteryModeCloudDisabledRepairFlow(RepairsFlow):
    """Handler for a battery mode/cloud incompatibility fix flow."""

    def __init__(self, entry: HomeWizardConfigEntry) -> None:
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
