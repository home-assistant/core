"""PTZ pulse-duration control for Agent DVR.

One button press moves the camera for a fixed pulse, then stops it. How
far that moves the camera per press depends on the camera and on taste —
this exposes that pulse duration as a number entity so it can be tuned
from the UI instead of hardcoded, without needing a code change.
"""

from typing import override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AgentDVRConfigEntry, AgentDVRData
from .const import DOMAIN

MIN_PULSE = 0.1
MAX_PULSE = 2.0
STEP_PULSE = 0.1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AgentDVRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PTZ pulse-duration number entity."""
    async_add_entities([AgentDVRPTZPulseNumber(entry.runtime_data)])


class AgentDVRPTZPulseNumber(NumberEntity):
    """How long (seconds) a PTZ button press moves the camera before stopping."""

    _attr_has_entity_name = True
    _attr_translation_key = "ptz_pulse_duration"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = MIN_PULSE
    _attr_native_max_value = MAX_PULSE
    _attr_native_step = STEP_PULSE
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: AgentDVRData) -> None:
        """Initialize the number entity."""
        self._data = data
        self._attr_unique_id = f"{data.unique_id}_ptz_pulse_duration"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, data.unique_id)})

    @property
    @override
    def native_value(self) -> float:
        """Return the configured pulse duration."""
        return self._data.ptz_pulse_seconds

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the pulse duration."""
        self._data.ptz_pulse_seconds = value
        self.async_write_ha_state()
