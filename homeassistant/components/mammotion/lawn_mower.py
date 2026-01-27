"""Luba lawn mowers."""

from __future__ import annotations

from pymammotion.data.model.report_info import DeviceData, ReportData
from pymammotion.utility.constant.device_constant import WorkMode

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MammotionConfigEntry, MammotionMowerUpdateCoordinator
from .const import COMMAND_EXCEPTIONS, DOMAIN, LOGGER
from .entity import MammotionBaseEntity

PARALLEL_UPDATES = 0


def get_entity_attribute(
    hass: HomeAssistant, entity_id: str, attribute_name: str
) -> str | None:
    """Get an attribute from an entity."""
    # Get the state object of the entity
    entity = hass.states.get(entity_id)

    # Check if the entity exists and has attributes
    if entity and attribute_name in entity.attributes:
        # Return the specific attribute
        return entity.attributes.get(attribute_name, None)
    # Return None if the entity or attribute does not exist
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Luba config entry."""
    mammotion_devices = entry.runtime_data.mowers
    entities: list[MammotionLawnMowerEntity] = [
        MammotionLawnMowerEntity(mower.coordinator) for mower in mammotion_devices
    ]
    async_add_entities(entities)


class MammotionLawnMowerEntity(MammotionBaseEntity, LawnMowerEntity):
    """Representation of a Mammotion lawn mower."""

    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
    )

    def __init__(self, coordinator: MammotionMowerUpdateCoordinator) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator, "mower")

    @property
    def rpt_dev_status(self) -> DeviceData:
        """Return the device status."""
        return self.coordinator.data.report_data.dev

    @property
    def report_data(self) -> ReportData:
        """Return the report data."""
        return self.coordinator.data.report_data

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the state of the mower."""

        charge_state = self.rpt_dev_status.charge_state
        mode = self.rpt_dev_status.sys_status

        LOGGER.debug("activity mode %s", mode)
        if mode == WorkMode.MODE_PAUSE or (
            mode == WorkMode.MODE_READY and charge_state == 0
        ):
            return LawnMowerActivity.PAUSED
        if mode == WorkMode.MODE_WORKING:
            return LawnMowerActivity.MOWING
        if mode == WorkMode.MODE_RETURNING:
            return LawnMowerActivity.RETURNING
        if mode == WorkMode.MODE_LOCK:
            return LawnMowerActivity.ERROR
        if mode == WorkMode.MODE_READY and charge_state != 0:
            return LawnMowerActivity.DOCKED
        return None

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        trans_key = "start_mowing_failed"

        mode = self.rpt_dev_status.sys_status
        if mode is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_not_ready"
            )

        if mode == WorkMode.MODE_PAUSE:
            trans_key = "resume_failed"
            try:
                await self.coordinator.async_send_command("resume_execute_task")
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key=trans_key
                ) from exc
            finally:
                await self.coordinator.api.async_request_iot_sync(
                    self.coordinator.device_name
                )

        else:
            try:
                await self.coordinator.async_send_command("start_job")
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key=trans_key
                ) from exc
            finally:
                await self.coordinator.api.async_request_iot_sync(
                    self.coordinator.device_name
                )

    async def async_dock(self) -> None:
        """Start docking."""
        trans_key = "pause_failed"

        charge_state = self.rpt_dev_status.charge_state
        mode = self.rpt_dev_status.sys_status
        if mode is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_not_ready"
            )

        if charge_state == 0 and mode in (
            WorkMode.MODE_WORKING,
            WorkMode.MODE_PAUSE,
            WorkMode.MODE_READY,
            WorkMode.MODE_RETURNING,
        ):
            try:
                if mode == WorkMode.MODE_WORKING:
                    trans_key = "pause_failed"
                    await self.coordinator.async_send_command("pause_execute_task")

                if mode == WorkMode.MODE_RETURNING:
                    trans_key = "dock_cancel_failed"
                    await self.coordinator.async_send_command("cancel_return_to_dock")
                else:
                    trans_key = "dock_failed"
                    await self.coordinator.async_send_command("return_to_dock")
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key=trans_key
                ) from exc
            finally:
                await self.coordinator.api.async_request_iot_sync(
                    self.coordinator.device_name
                )

    async def async_pause(self) -> None:
        """Pause mower."""
        trans_key = "pause_failed"

        mode = self.rpt_dev_status.sys_status
        if mode is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_not_ready"
            )

        if mode in (
            WorkMode.MODE_WORKING,
            WorkMode.MODE_RETURNING,
        ):
            try:
                if mode == WorkMode.MODE_WORKING:
                    trans_key = "pause_failed"
                    await self.coordinator.async_send_command("pause_execute_task")
                if mode == WorkMode.MODE_RETURNING:
                    trans_key = "dock_cancel_failed"
                    await self.coordinator.async_send_command("cancel_return_to_dock")
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key=trans_key
                ) from exc
            finally:
                await self.coordinator.api.async_request_iot_sync(
                    self.coordinator.device_name
                )
