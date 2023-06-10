"""Support for the MirAIe climate."""

from __future__ import annotations

import logging
from typing import Any

from py_miraie_ac import (
    Device as MirAIeDevice,
    FanMode as MirAIeFanMode,
    Home as MirAIeHome,
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
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add MirAIe AC devices."""
    api: MirAIeAPI = hass.data[DOMAIN][entry.entry_id]
    home: MirAIeHome = await api.initialize()
    devices: list[MirAIeDevice] = []

    for _device_id, device in home.devices.items():
        _LOGGER.debug("Found MirAIe device: %s", device.friendly_name)
        devices.append(device)

    entities = list(map(MirAIeClimateEntity, devices))
    async_add_entities(entities)


class MirAIeClimateEntity(ClimateEntity):
    """Define MirAIe Climate."""

    def __init__(self, device: MirAIeDevice) -> None:
        """Initialize MirAIe climate entity."""
        self._attr_hvac_modes = [
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.OFF,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
        self._attr_fan_mode = FAN_OFF
        self._attr_fan_modes = [
            FAN_AUTO,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
            FAN_OFF,
        ]
        self._attr_swing_modes = [
            SWING_ON,
            SWING_OFF,
            SWING_VERTICAL,
            SWING_HORIZONTAL,
            SWING_BOTH,
        ]
        self._attr_max_temp = 30.0
        self._attr_min_temp = 16.0
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_WHOLE
        self._attr_unique_id = device.device_id
        self.device = device

        _LOGGER.debug("MirAIe device added: %s", device.friendly_name)

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self.device.friendly_name

    @property
    def icon(self) -> str | None:
        """Return the icon to use on the frontend, if any."""
        return "mdi:air-conditioner"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            name=self.device.friendly_name,
            manufacturer=self.device.brand,
            model=self.device.model_number,
            sw_version=self.device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        _LOGGER.debug(
            "%s availability queried: %s",
            self.device.friendly_name,
            self.device.status.is_online,
        )

        return self.device.status.is_online

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Gets the current HVAC Mode."""
        power_mode = self.device.status.power_mode
        _LOGGER.debug(
            "%s hvac mode queried: %s",
            self.device.friendly_name,
            self.device.status.power_mode,
        )

        if power_mode.value == MirAIePowerMode.OFF:
            return HVACMode.OFF

        hvac_mode = self.device.status.hvac_mode

        if hvac_mode == MirAIeHVACMode.FAN:
            return HVACMode.FAN_ONLY

        return hvac_mode.value

    @property
    def current_temperature(self) -> float | None:
        """Gets the current room temperature."""
        _LOGGER.debug(
            "%s current temp queried: %s",
            self.device.friendly_name,
            self.device.status.room_temp,
        )
        return self.device.status.room_temp

    @property
    def target_temperature(self) -> float | None:
        """Gets the current target temperature."""
        _LOGGER.debug(
            "%s target temp queried: %s",
            self.device.friendly_name,
            self.device.status.temperature,
        )
        return self.device.status.temperature

    @property
    def preset_mode(self) -> str | None:
        """Get the current Preset Mode."""
        _LOGGER.debug(
            "%s preset mode queried: %s",
            self.device.friendly_name,
            self.device.status.preset_mode.value,
        )
        return self.device.status.preset_mode.value

    @property
    def fan_mode(self) -> str | None:
        """Gets the current Fan Mode."""
        _LOGGER.debug(
            "%s fan mode queried: %s",
            self.device.friendly_name,
            self.device.status.fan_mode,
        )
        mode = self.device.status.fan_mode

        if mode == MirAIeFanMode.QUIET:
            return FAN_LOW
        return mode.HIGH

    @property
    def swing_mode(self) -> str | None:
        """Gets the current Swing Mode."""
        _LOGGER.debug(
            "%s swing mode queried: %s",
            self.device.friendly_name,
            self.device.status.swing_mode,
        )
        mode = self.device.status.swing_mode

        if mode == MirAIeSwingMode.ONE:
            return SWING_OFF
        return SWING_ON

    def set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError("No target temperature provided")

        _LOGGER.debug(
            "%s temp set: %s",
            self.device.friendly_name,
            temperature,
        )
        self.device.set_temperature(temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug(
            "%s hvac mode set: %s",
            self.device.friendly_name,
            hvac_mode.value,
        )

        if hvac_mode == HVACMode.OFF:
            self.device.turn_off()
        else:
            if self.device.status.power_mode == MirAIePowerMode.OFF:
                self.device.turn_on()

            if hvac_mode == HVACMode.FAN_ONLY:
                self.device.set_hvac_mode(MirAIeHVACMode.FAN)
            else:
                self.device.set_hvac_mode(MirAIeHVACMode(hvac_mode.value))

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        _LOGGER.debug(
            "%s fan mode set: %s",
            self.device.friendly_name,
            fan_mode,
        )

        if fan_mode == FAN_OFF:
            self.device.set_fan_mode(MirAIeFanMode.QUIET)
        else:
            self.device.set_fan_mode(MirAIeFanMode(fan_mode))

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set Swing mode."""
        _LOGGER.debug(
            "%s swing mode set: %s",
            self.device.friendly_name,
            swing_mode,
        )

        if swing_mode == SWING_ON:
            self.device.set_swing_mode(MirAIeSwingMode.AUTO)
        else:
            self.device.set_swing_mode(MirAIeSwingMode.ONE)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        _LOGGER.debug(
            "%s preset mode set: %s",
            self.device.friendly_name,
            preset_mode,
        )
        self.device.set_preset_mode(MirAIePresetMode(preset_mode))

    # async def async_added_to_hass(self) -> None:
    #     """Run when this Entity has been added to HA."""
    #     self.device.registerCallback(self.async_write_ha_state)

    # async def async_will_remove_from_hass(self) -> None:
    #     """Entity being removed from hass."""
    #     self.device.removeCallback(self.async_write_ha_state)
