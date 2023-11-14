"""Support for the MirAIe climate."""

from __future__ import annotations

import logging
from typing import Any

from py_miraie_ac import (
    Device as MirAIeDevice,
    FanMode as MirAIeFanMode,
    HVACMode as MirAIeHVACMode,
    MirAIeAPI,
    PowerMode as MirAIePowerMode,
    PresetMode as MirAIePresetMode,
    SwingMode as MirAIeSwingMode,
)

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRECISION_WHOLE,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

# max and min values supported by the devices
MAX_TEMP = 30.0
MIN_TEMP = 16.0

HVAC_MODE_MAP_TO_HASS = {
    MirAIeHVACMode.COOL: HVACMode.COOL,
    MirAIeHVACMode.AUTO: HVACMode.AUTO,
    MirAIeHVACMode.DRY: HVACMode.DRY,
    MirAIeHVACMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_MAP_TO_MIRAIE = {
    HVACMode.AUTO: MirAIeHVACMode.AUTO,
    HVACMode.COOL: MirAIeHVACMode.COOL,
    HVACMode.DRY: MirAIeHVACMode.DRY,
    HVACMode.FAN_ONLY: MirAIeHVACMode.FAN,
}

PRESET_MODE_MAP_TO_HASS = {
    MirAIePresetMode.BOOST: PRESET_BOOST,
    MirAIePresetMode.ECO: PRESET_ECO,
    MirAIePresetMode.NONE: PRESET_NONE,
}

PRESET_MODE_MAP_TO_MIRAIE = {
    PRESET_BOOST: MirAIePresetMode.BOOST,
    PRESET_ECO: MirAIePresetMode.ECO,
    PRESET_NONE: MirAIePresetMode.NONE,
}

FAN_MODE_MAP_TO_HASS = {
    MirAIeFanMode.AUTO: FAN_AUTO,
    MirAIeFanMode.HIGH: FAN_HIGH,
    MirAIeFanMode.LOW: FAN_LOW,
    MirAIeFanMode.MEDIUM: FAN_MEDIUM,
    MirAIeFanMode.QUIET: FAN_OFF,
}

FAN_MODE_MAP_TO_MIRAIE = {
    FAN_AUTO: MirAIeFanMode.AUTO,
    FAN_HIGH: MirAIeFanMode.HIGH,
    FAN_LOW: MirAIeFanMode.LOW,
    FAN_MEDIUM: MirAIeFanMode.MEDIUM,
    FAN_OFF: MirAIeFanMode.QUIET,
}


SUPPORTED_HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.OFF,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]

SUPPORTED_PRESET_MODES = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
SUPPORTED_FAN_MODES = [
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,
]

SUPPORTED_SWING_MODES = [
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
]

SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.SWING_MODE
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add MirAIe AC devices."""
    api: MirAIeAPI = hass.data[DOMAIN][entry.entry_id]
    devices: list[MirAIeDevice] = api.devices
    entities = list(map(MirAIeClimateEntity, devices))
    async_add_entities(entities)


class MirAIeClimateEntity(ClimateEntity):
    """Define MirAIe Climate."""

    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_preset_modes = SUPPORTED_PRESET_MODES
    _attr_fan_modes = SUPPORTED_FAN_MODES
    _attr_swing_modes = SUPPORTED_SWING_MODES
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_fan_mode = FAN_OFF
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_icon = "mdi:air-conditioner"

    def __init__(self, device: MirAIeDevice) -> None:
        """Initialize MirAIe climate entity."""

        self._device = device
        self._friendly_name = device.friendly_name

        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.friendly_name,
            manufacturer=device.brand,
            model=device.model_number,
            sw_version=device.firmware_version,
            suggested_area=device.area_name,
        )

        self._update_entity()
        _LOGGER.debug("MirAIe device added: %s", device.friendly_name)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError("No Target Temperature provided")

        self._device.set_temperature(temperature)
        _LOGGER.debug(
            "%s - Target Temperature set: %s",
            self._friendly_name,
            temperature,
        )

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug(
            "%s - HVAC Mode set: %s",
            self._friendly_name,
            hvac_mode.value,
        )

        if hvac_mode == HVACMode.OFF:
            self._device.turn_off()
            return

        if self._device.status.power_mode == MirAIePowerMode.OFF:
            self._device.turn_on()

        self._device.set_hvac_mode(HVAC_MODE_MAP_TO_MIRAIE[hvac_mode])

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        self._device.set_fan_mode(FAN_MODE_MAP_TO_MIRAIE[fan_mode])
        _LOGGER.debug(
            "%s fan mode set: %s",
            self._friendly_name,
            fan_mode,
        )

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set Swing mode."""

        if swing_mode == SWING_BOTH:
            self._device.set_vertical_swing_mode(MirAIeSwingMode.AUTO)
            self._device.set_horizontal_swing_mode(MirAIeSwingMode.AUTO)
        elif swing_mode == SWING_HORIZONTAL:
            self._device.set_vertical_swing_mode(MirAIeSwingMode.ONE)
            self._device.set_horizontal_swing_mode(MirAIeSwingMode.AUTO)
        elif swing_mode == SWING_VERTICAL:
            self._device.set_vertical_swing_mode(MirAIeSwingMode.AUTO)
            self._device.set_horizontal_swing_mode(MirAIeSwingMode.ONE)
        elif swing_mode == SWING_OFF:
            self._device.set_vertical_swing_mode(MirAIeSwingMode.ONE)
            self._device.set_horizontal_swing_mode(MirAIeSwingMode.ONE)

        _LOGGER.debug(
            "%s swing mode set: %s",
            self._friendly_name,
            swing_mode,
        )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        self._device.set_preset_mode(PRESET_MODE_MAP_TO_MIRAIE[preset_mode])

        _LOGGER.debug(
            "%s preset mode set: %s",
            self._friendly_name,
            preset_mode,
        )

    def _map_swing_mode(
        self, v_swing: MirAIeSwingMode, h_swing: MirAIeSwingMode
    ) -> str:
        if v_swing == MirAIeSwingMode.AUTO and h_swing == MirAIeSwingMode.AUTO:
            return SWING_BOTH

        if MirAIeSwingMode.AUTO not in (v_swing, h_swing):
            return SWING_OFF

        if v_swing == MirAIeSwingMode.AUTO:
            return SWING_VERTICAL

        return SWING_HORIZONTAL

    def _update_entity(self):
        self._attr_available = self._device.status.is_online
        self._attr_current_temperature = self._device.status.room_temp
        self._attr_target_temperature = self._device.status.temperature

        # preset mode
        preset_mode = self._device.status.preset_mode
        self._attr_preset_mode = (
            PRESET_NONE if preset_mode is None else PRESET_MODE_MAP_TO_HASS[preset_mode]
        )

        # fan mode
        fan_mode = self._device.status.fan_mode
        self._attr_fan_mode = FAN_MODE_MAP_TO_HASS[fan_mode]

        # swing mode
        v_swing_mode = self._device.status.vertical_swing_mode
        h_swing_mode = self._device.status.horizontal_swing_mode
        self._attr_swing_mode = self._map_swing_mode(v_swing_mode, h_swing_mode)

        # hvac mode
        power_mode = self._device.status.power_mode
        hvac_mode = self._device.status.hvac_mode
        self._attr_hvac_mode = (
            HVACMode.OFF
            if power_mode == MirAIePowerMode.OFF
            else HVAC_MODE_MAP_TO_HASS[hvac_mode]
        )

    def entity_state_changed_callback(self):
        """Device status has changed, notify Hass that the entity state must be updated."""

        self._update_entity()
        _LOGGER.debug("%s - Hass State Updated", self._friendly_name)
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._device.register_callback(self.entity_state_changed_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._device.remove_callback(self.entity_state_changed_callback)
