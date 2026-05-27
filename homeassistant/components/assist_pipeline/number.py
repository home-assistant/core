"""Number entities for assist pipeline settings."""

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant

from .vad import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    MAX_COMMAND_TIMEOUT_SECONDS,
    MIN_COMMAND_TIMEOUT_SECONDS,
)


class CommandTimeoutNumber(RestoreNumber):
    """Entity to represent command timeout seconds."""

    entity_description = NumberEntityDescription(
        key="command_timeout",
        translation_key="command_timeout",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_min_value = MIN_COMMAND_TIMEOUT_SECONDS
    _attr_native_max_value = MAX_COMMAND_TIMEOUT_SECONDS
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_native_value = DEFAULT_COMMAND_TIMEOUT_SECONDS

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a command timeout number."""
        self._attr_unique_id = f"{unique_id_prefix}-command_timeout"
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = float(
            max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        )
        self.async_write_ha_state()
