"""Number platform for SwitchBot devices."""

from datetime import timedelta
import logging

import switchbot
from switchbot import SwitchbotOperationError
from switchbot.devices.meter_pro import MAX_TIME_OFFSET

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CURTAIN_SPEED_MAX, CURTAIN_SPEED_MIN, DEFAULT_CURTAIN_SPEED
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(days=7)
_LOGGER = logging.getLogger(__name__)
_SECONDS_IN_MINUTE = 60
_MAX_TIME_OFFSET_MINUTES = MAX_TIME_OFFSET // _SECONDS_IN_MINUTE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot number platform."""
    coordinator = entry.runtime_data

    if isinstance(coordinator.device, switchbot.SwitchbotMeterProCO2):
        async_add_entities(
            [SwitchBotMeterProCO2DisplayTimeOffsetNumber(coordinator)], True
        )
    elif isinstance(coordinator.device, switchbot.SwitchbotCurtain):
        async_add_entities(
            [SwitchBotCurtainSpeedNumber(coordinator)],
        )


class SwitchBotMeterProCO2DisplayTimeOffsetNumber(SwitchbotEntity, NumberEntity):
    """Number entity to set the time offset for Meter Pro CO2 devices."""

    _device: switchbot.SwitchbotMeterProCO2
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "display_time_offset"
    _attr_native_min_value = -_MAX_TIME_OFFSET_MINUTES
    _attr_native_max_value = _MAX_TIME_OFFSET_MINUTES
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_should_poll = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_display_time_offset"

    @exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the time offset."""
        _LOGGER.debug("Setting time offset to %s minutes for %s", value, self._address)
        offset_minutes = round(value)
        offset_seconds = offset_minutes * _SECONDS_IN_MINUTE
        await self._device.set_time_offset(offset_seconds)
        self._attr_native_value = offset_minutes
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the latest time offset from the device."""
        try:
            offset_seconds = await self._device.get_time_offset()
        except SwitchbotOperationError:
            _LOGGER.debug(
                "Failed to update time offset for %s", self._address, exc_info=True
            )
            return
        self._attr_native_value = round(offset_seconds / _SECONDS_IN_MINUTE)


class SwitchBotCurtainSpeedNumber(SwitchbotEntity, RestoreNumber):
    """Exposes curtain speed as a number entity so it can be configured dynamically."""

    _device: switchbot.SwitchbotCurtain
    _attr_native_min_value = float(CURTAIN_SPEED_MIN)
    _attr_native_max_value = float(CURTAIN_SPEED_MAX)
    _attr_native_step = 1.0
    _attr_native_value: float = float(DEFAULT_CURTAIN_SPEED)
    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description = NumberEntityDescription(
        key="curtain_speed",
        translation_key="curtain_speed",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_curtain_speed"
        if self.coordinator.curtain_speed is None:
            self.coordinator.curtain_speed = self.native_value

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        if (last_number_data is not None) and (
            last_number_data.native_value is not None
        ):
            await self.async_set_native_value(float(last_number_data.native_value))

    @exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the curtain speed."""
        self._attr_native_value = value
        self.coordinator.curtain_speed = value

        self.async_write_ha_state()
