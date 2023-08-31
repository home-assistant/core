"""Support for the MirAIe climate."""

from __future__ import annotations

import logging
from typing import Any

from py_miraie_ac import (
    Device as MirAIeDevice,
    MirAIeAPI,
    PowerMode as MirAIePowerMode,
    SwingMode as MirAIeSwingMode,
)

from homeassistant.components.climate import (
    FAN_OFF,
    PRECISION_WHOLE,
    PRESET_NONE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import (
    FAN_MODE_MAP_TO_HASS,
    FAN_MODE_MAP_TO_MIRAIE,
    HVAC_MODE_MAP_TO_HASS,
    HVAC_MODE_MAP_TO_MIRAIE,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_MODE_MAP_TO_HASS,
    PRESET_MODE_MAP_TO_MIRAIE,
    SUPPORTED_FAN_MODES,
    SUPPORTED_FEATURES,
    SUPPORTED_HVAC_MODES,
    SUPPORTED_PRESET_MODES,
    SUPPORTED_SWING_MODES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add MirAIe AC devices."""
    api: MirAIeAPI = hass.data[DOMAIN][entry.entry_id]
    await api.initialize()
    devices: list[MirAIeDevice] = api.devices

    for device in devices:
        _LOGGER.debug("Found MirAIe device: %s", device.friendly_name)

    entities = list(map(MirAIeClimateEntity, devices))
    async_add_entities(entities)


class MirAIeClimateEntity(ClimateEntity):
    """Define MirAIe Climate."""

    def __init__(self, device: MirAIeDevice) -> None:
        """Initialize MirAIe climate entity."""
        self._attr_hvac_modes = SUPPORTED_HVAC_MODES
        self._attr_preset_modes = SUPPORTED_PRESET_MODES
        self._attr_fan_modes = SUPPORTED_FAN_MODES
        self._attr_swing_modes = SUPPORTED_SWING_MODES
        self._attr_supported_features = SUPPORTED_FEATURES
        self._attr_fan_mode = FAN_OFF
        self._attr_max_temp = MAX_TEMP
        self._attr_min_temp = MIN_TEMP
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_WHOLE
        self._attr_unique_id = device.device_id
        self._friendly_name = device.friendly_name
        self.device = device

        _LOGGER.debug("MirAIe device added: %s", device.friendly_name)

    @property
    def should_poll(self) -> bool:
        """Let Hass know that polling is not required."""
        return False

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._friendly_name

    @property
    def icon(self) -> str | None:
        """Return the icon to use on the frontend, if any."""
        return "mdi:air-conditioner"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            name=self._friendly_name,
            manufacturer=self.device.brand,
            model=self.device.model_number,
            sw_version=self.device.firmware_version,
            suggested_area=self.device.area_name,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        _LOGGER.debug(
            "%s - Availability queried: %s",
            self._friendly_name,
            self.device.status.is_online,
        )

        return self.device.status.is_online

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Gets the current HVAC Mode."""
        power_mode = self.device.status.power_mode
        hvac_mode = self.device.status.hvac_mode

        result = (
            HVACMode.OFF
            if power_mode == MirAIePowerMode.OFF
            else HVAC_MODE_MAP_TO_HASS[hvac_mode]
        )

        _LOGGER.debug(
            "%s - HVAC mode queried: %s",
            self._friendly_name,
            result,
        )

        return result

    @property
    def current_temperature(self) -> float | None:
        """Gets the current room temperature."""
        _LOGGER.debug(
            "%s - Room Temperature queried: %s",
            self._friendly_name,
            self.device.status.room_temp,
        )

        return self.device.status.room_temp

    @property
    def target_temperature(self) -> float | None:
        """Gets the current target temperature."""
        _LOGGER.debug(
            "%s - Target Temperature queried: %s",
            self._friendly_name,
            self.device.status.temperature,
        )

        return self.device.status.temperature

    @property
    def preset_mode(self) -> str | None:
        """Get the current Preset Mode."""
        preset_mode = self.device.status.preset_mode
        result = (
            PRESET_NONE if preset_mode is None else PRESET_MODE_MAP_TO_HASS[preset_mode]
        )

        _LOGGER.debug(
            "%s - Preset Mode queried: %s",
            self._friendly_name,
            result,
        )

        return result

    @property
    def fan_mode(self) -> str | None:
        """Gets the current Fan Mode."""
        fan_mode = self.device.status.fan_mode

        result = FAN_MODE_MAP_TO_HASS[fan_mode]
        _LOGGER.debug("%s - Fan Mode queried: %s", self._friendly_name, result)
        return result

    @property
    def swing_mode(self) -> str | None:
        """Gets the current Swing Mode."""
        v_swing_mode = self.device.status.vertical_swing_mode
        h_swing_mode = self.device.status.horizontal_swing_mode

        result = self._map_swing_mode(v_swing_mode, h_swing_mode)
        _LOGGER.debug("%s - Swing mode queried: %s", self._friendly_name, result)
        return result

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

    def set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError("No Target Temperature provided")

        self.device.set_temperature(temperature)
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
            self.device.turn_off()
            return

        if self.device.status.power_mode == MirAIePowerMode.OFF:
            self.device.turn_on()

        self.device.set_hvac_mode(HVAC_MODE_MAP_TO_MIRAIE[hvac_mode])

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        self.device.set_fan_mode(FAN_MODE_MAP_TO_MIRAIE[fan_mode])
        _LOGGER.debug(
            "%s fan mode set: %s",
            self._friendly_name,
            fan_mode,
        )

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set Swing mode."""

        if swing_mode == SWING_BOTH:
            self.device.set_vertical_swing_mode(MirAIeSwingMode.AUTO)
            self.device.set_horizontal_swing_mode(MirAIeSwingMode.AUTO)
        elif swing_mode == SWING_HORIZONTAL:
            self.device.set_vertical_swing_mode(MirAIeSwingMode.ONE)
            self.device.set_horizontal_swing_mode(MirAIeSwingMode.AUTO)
        elif swing_mode == SWING_VERTICAL:
            self.device.set_vertical_swing_mode(MirAIeSwingMode.AUTO)
            self.device.set_horizontal_swing_mode(MirAIeSwingMode.ONE)
        elif swing_mode == SWING_OFF:
            self.device.set_vertical_swing_mode(MirAIeSwingMode.ONE)
            self.device.set_horizontal_swing_mode(MirAIeSwingMode.ONE)

        _LOGGER.debug(
            "%s swing mode set: %s",
            self._friendly_name,
            swing_mode,
        )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        self.device.set_preset_mode(PRESET_MODE_MAP_TO_MIRAIE[preset_mode])

        _LOGGER.debug(
            "%s preset mode set: %s",
            self._friendly_name,
            preset_mode,
        )

    def entity_state_changed_callback(self):
        """Device status has changed, notify Hass that the entity state must be updated."""
        _LOGGER.debug("%s - Hass State Updated", self._friendly_name)
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self.device.register_callback(self.entity_state_changed_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self.device.remove_callback(self.entity_state_changed_callback)
