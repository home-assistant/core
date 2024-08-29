"""Luba lawn mowers."""

from __future__ import annotations

from pymammotion.mammotion.devices.mammotion import has_field
from pymammotion.proto.luba_msg import RptDevStatus
from pymammotion.utility.constant.device_constant import WorkMode

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MammotionConfigEntry
from .const import COMMAND_EXCEPTIONS, DOMAIN, LOGGER
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Luba config entry."""
    coordinator = entry.runtime_data
    async_add_entities([MammotionLawnMowerEntity(coordinator)])


class MammotionLawnMowerEntity(MammotionBaseEntity, LawnMowerEntity):
    """Representation of a Mammotion lawn mower."""

    _attr_supported_features = (
        LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
    )

    def __init__(self, coordinator: MammotionDataUpdateCoordinator) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator, "mower")
        self._attr_name = None  # main feature of device

    @property
    def rpt_dev_status(self) -> RptDevStatus | None:
        """Return the device status."""
        if has_field(self.coordinator.data.sys.toapp_report_data.dev):
            return self.coordinator.data.sys.toapp_report_data.dev
        return None

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the state of the mower."""

        if self.rpt_dev_status is None:
            return None

        mode = self.rpt_dev_status.sys_status
        charge_state = self.rpt_dev_status.charge_state

        LOGGER.debug("activity mode %s", mode)
        if (
            mode == WorkMode.MODE_PAUSE
            or mode == WorkMode.MODE_READY
            and charge_state == 0
        ):
            return LawnMowerActivity.PAUSED
        if mode in (WorkMode.MODE_WORKING, WorkMode.MODE_RETURNING):
            return LawnMowerActivity.MOWING
        if mode == WorkMode.MODE_LOCK:
            return LawnMowerActivity.ERROR
        if mode == WorkMode.MODE_READY and charge_state != 0:
            return LawnMowerActivity.DOCKED
        return None

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        # check if job in progress
        #
        if self.rpt_dev_status is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_not_ready"
            )
        if self.rpt_dev_status.sys_status == WorkMode.MODE_PAUSE:
            try:
                await self.coordinator.async_send_command("resume_execute_task")
                return await self.coordinator.async_request_iot_sync()
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="resume_failed"
                ) from exc
        try:
            await self.coordinator.async_send_command("start_job")
            await self.coordinator.async_request_iot_sync()
        except COMMAND_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="start_failed"
            ) from exc
        finally:
            self.coordinator.async_set_updated_data(
                self.coordinator.manager.mower(self.coordinator.device_name)
            )

    async def async_dock(self) -> None:
        """Start docking."""

        mode = self.rpt_dev_status.sys_status

        try:
            if mode == WorkMode.MODE_RETURNING:
                await self.coordinator.async_send_command("cancel_return_to_dock")
                return await self.coordinator.async_send_command("get_report_cfg")
            if mode == WorkMode.MODE_WORKING:
                await self.coordinator.async_send_command("pause_execute_task")
            await self.coordinator.async_send_command("return_to_dock")
            await self.coordinator.async_request_iot_sync()
        except COMMAND_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="dock_failed"
            ) from exc
        finally:
            self.coordinator.async_set_updated_data(
                self.coordinator.manager.mower(self.coordinator.device_name)
            )

    async def async_pause(self) -> None:
        """Pause mower."""
        try:
            await self.coordinator.async_send_command("pause_execute_task")
            await self.coordinator.async_request_iot_sync()
        except COMMAND_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pause_failed"
            ) from exc
        finally:
            self.coordinator.async_set_updated_data(
                self.coordinator.manager.mower(self.coordinator.device_name)
            )
