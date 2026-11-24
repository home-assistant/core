"""Luba lawn mowers."""

from collections.abc import Awaitable
from typing import override

from pymammotion.data.model.report_info import DeviceData
from pymammotion.utility.constant.device_constant import WorkMode

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MammotionConfigEntry
from .const import COMMAND_EXCEPTIONS, DOMAIN
from .coordinator import MammotionMowerUpdateCoordinator
from .entity import MammotionBaseEntity

# Serialized so an action cannot interleave with another one waiting on the mower.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Luba config entry."""
    async_add_entities(
        MammotionLawnMowerEntity(mower.coordinator)
        for mower in entry.runtime_data.mowers
    )


class MammotionLawnMowerEntity(MammotionBaseEntity, LawnMowerEntity):
    """Representation of a Mammotion lawn mower."""

    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.STOP
    )

    def __init__(self, coordinator: MammotionMowerUpdateCoordinator) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator, "mower")

    @property
    def rpt_dev_status(self) -> DeviceData:
        """Return the device status."""
        return self.coordinator.data.report_data.dev

    @override
    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the state of the mower."""
        charge_state = self.rpt_dev_status.charge_state
        mode = self.rpt_dev_status.sys_status

        if mode in (WorkMode.MODE_PAUSE, WorkMode.MODE_CHARGING_PAUSE):
            return LawnMowerActivity.PAUSED
        if mode == WorkMode.MODE_WORKING:
            return LawnMowerActivity.MOWING
        if mode == WorkMode.MODE_RETURNING:
            return LawnMowerActivity.RETURNING
        if mode == WorkMode.MODE_LOCK:
            return LawnMowerActivity.ERROR
        if mode == WorkMode.MODE_READY and charge_state == 0:
            return LawnMowerActivity.IDLE
        if mode == WorkMode.MODE_READY and charge_state != 0:
            return LawnMowerActivity.DOCKED
        return None

    async def _async_step[T](self, step: Awaitable[T], translation_key: str) -> T:
        """Await one step of an action, raising the translated error if it fails."""
        try:
            return await step
        except COMMAND_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from exc

    async def _async_send(self, command: str, translation_key: str) -> None:
        """Send a command, raising the translated error if it does not land."""
        await self._async_step(
            self.coordinator.async_send_command(command), translation_key
        )

    async def _async_wait_for_mode(
        self, translation_key: str, *modes: WorkMode
    ) -> WorkMode:
        """Wait for the mower to report one of the modes."""
        return await self._async_step(
            self.coordinator.async_wait_for_mode(*modes), translation_key
        )

    @override
    async def async_start_mowing(self) -> None:
        """Start mowing."""
        try:
            # A mower recharging mid-job resumes it, as a paused one does.
            if self.rpt_dev_status.sys_status in (
                WorkMode.MODE_PAUSE,
                WorkMode.MODE_CHARGING_PAUSE,
            ):
                await self._async_send("resume_execute_task", "resume_failed")
            else:
                await self._async_send("start_job", "start_failed")
        finally:
            await self.coordinator.async_request_report()

    @override
    async def async_dock(self) -> None:
        """Start docking."""
        mode = self.rpt_dev_status.sys_status
        # MODE_RETURNING is left untouched; the mower is already docking
        if self.rpt_dev_status.charge_state != 0 or mode not in (
            WorkMode.MODE_WORKING,
            WorkMode.MODE_PAUSE,
            WorkMode.MODE_READY,
        ):
            return
        try:
            if mode == WorkMode.MODE_WORKING:
                await self._async_send("pause_execute_task", "pause_failed")
            await self._async_send("return_to_dock", "dock_failed")
        finally:
            await self.coordinator.async_request_report()

    @override
    async def async_pause(self) -> None:
        """Pause mower."""
        mode = self.rpt_dev_status.sys_status
        if mode not in (WorkMode.MODE_WORKING, WorkMode.MODE_RETURNING):
            return
        try:
            if mode == WorkMode.MODE_WORKING:
                await self._async_send("pause_execute_task", "pause_failed")
            else:
                await self._async_send("cancel_return_to_dock", "dock_cancel_failed")
        finally:
            await self.coordinator.async_request_report()

    @override
    async def async_stop(self) -> None:
        """Cancel the current job without sending the mower back to the dock."""
        mode = self.rpt_dev_status.sys_status
        if mode not in (
            WorkMode.MODE_WORKING,
            WorkMode.MODE_PAUSE,
            WorkMode.MODE_CHARGING_PAUSE,
            WorkMode.MODE_RETURNING,
        ):
            return
        try:
            # The mower only takes cancel_job once it has come to a pause.
            if mode == WorkMode.MODE_WORKING:
                await self._async_send("pause_execute_task", "pause_failed")
                mode = await self._async_wait_for_mode(
                    "pause_failed", WorkMode.MODE_PAUSE
                )
            elif mode == WorkMode.MODE_RETURNING:
                await self._async_send("cancel_return_to_dock", "dock_cancel_failed")
                mode = await self._async_wait_for_mode(
                    "dock_cancel_failed", WorkMode.MODE_PAUSE, WorkMode.MODE_READY
                )
            if mode in (WorkMode.MODE_PAUSE, WorkMode.MODE_CHARGING_PAUSE):
                await self._async_send("cancel_job", "stop_failed")
        finally:
            await self.coordinator.async_request_report()
