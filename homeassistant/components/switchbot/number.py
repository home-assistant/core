"""Number platform for SwitchBot devices."""

from datetime import timedelta
import logging

import switchbot
from switchbot import SwitchbotOperationError
from switchbot.devices.meter_pro import MAX_TIME_OFFSET

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
