"""Number entities for assist pipeline settings."""

from typing import Final

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant

from .vad import DEFAULT_VAD_SILENCE_SECONDS, DEFAULT_VAD_TIMEOUT_SECONDS

MIN_VAD_SILENCE_SECONDS: Final = 0.1
MAX_VAD_SILENCE_SECONDS: Final = 5.0
MIN_VAD_TIMEOUT_SECONDS: Final = 1.0
MAX_VAD_TIMEOUT_SECONDS: Final = 120.0


class VadSilenceSecondsNumber(RestoreNumber):
    """Entity to represent VAD end-of-speech silence seconds."""

    entity_description = NumberEntityDescription(
        key="vad_silence_seconds",
        translation_key="vad_silence_seconds",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = MIN_VAD_SILENCE_SECONDS
    _attr_native_max_value = MAX_VAD_SILENCE_SECONDS
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_native_value = DEFAULT_VAD_SILENCE_SECONDS

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a VAD silence seconds number."""
        self._attr_unique_id = f"{unique_id_prefix}-vad_silence_seconds"
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self._async_restore_native_value()

    async def _async_restore_native_value(self) -> None:
        """Restore the last native value."""
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = float(
            max(MIN_VAD_SILENCE_SECONDS, min(MAX_VAD_SILENCE_SECONDS, value))
        )
        self.async_write_ha_state()


class VadTimeoutSecondsNumber(RestoreNumber):
    """Entity to represent VAD command timeout seconds."""

    entity_description = NumberEntityDescription(
        key="vad_timeout_seconds",
        translation_key="vad_timeout_seconds",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_native_min_value = MIN_VAD_TIMEOUT_SECONDS
    _attr_native_max_value = MAX_VAD_TIMEOUT_SECONDS
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_native_value = DEFAULT_VAD_TIMEOUT_SECONDS

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a VAD timeout seconds number."""
        self._attr_unique_id = f"{unique_id_prefix}-vad_timeout_seconds"
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self._async_restore_native_value()

    async def _async_restore_native_value(self) -> None:
        """Restore the last native value."""
        last_number_data = await self.async_get_last_number_data()
        if last_number_data is not None and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = float(
            max(MIN_VAD_TIMEOUT_SECONDS, min(MAX_VAD_TIMEOUT_SECONDS, value))
        )
        self.async_write_ha_state()
