"""Support for KNX/IP climate devices."""
from typing import List, Optional

from xknx.devices import Climate as XknxClimate
from xknx.dpt import HVACOperationMode

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import DOMAIN, OPERATION_MODES, PRESET_MODES
from .knx_entity import KnxEntity

OPERATION_MODES_INV = dict(reversed(item) for item in OPERATION_MODES.items())
PRESET_MODES_INV = dict(reversed(item) for item in PRESET_MODES.items())


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up climate(s) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxClimate):
            entities.append(KNXClimate(device))
    async_add_entities(entities)


class KNXClimate(KnxEntity, ClimateEntity):
    """Representation of a KNX climate device."""

    def __init__(self, device: XknxClimate):
        """Initialize of a KNX climate device."""
        super().__init__(device)

        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    async def async_update(self):
        """Request a state update from KNX bus."""
        await self._device.sync()
        await self._device.mode.sync()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.temperature.value

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._device.temperature_step

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature.value

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.target_temperature_min

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.target_temperature_max

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_target_temperature(temperature)
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        if self._device.supports_on_off and not self._device.is_on:
            return HVAC_MODE_OFF
        if self._device.mode.supports_operation_mode:
            return OPERATION_MODES.get(
                self._device.mode.operation_mode.value, HVAC_MODE_HEAT
            )
        # default to "heat"
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> Optional[List[str]]:
        """Return the list of available operation modes."""
        _operations = [
            OPERATION_MODES.get(operation_mode.value)
            for operation_mode in self._device.mode.operation_modes
        ]

        if self._device.supports_on_off:
            if not _operations:
                _operations.append(HVAC_MODE_HEAT)
            _operations.append(HVAC_MODE_OFF)

        _modes = list(set(filter(None, _operations)))
        # default to ["heat"]
        return _modes if _modes else [HVAC_MODE_HEAT]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set operation mode."""
        if self._device.supports_on_off and hvac_mode == HVAC_MODE_OFF:
            await self._device.turn_off()
        else:
            if self._device.supports_on_off and not self._device.is_on:
                await self._device.turn_on()
            if self._device.mode.supports_operation_mode:
                knx_operation_mode = HVACOperationMode(
                    OPERATION_MODES_INV.get(hvac_mode)
                )
                await self._device.mode.set_operation_mode(knx_operation_mode)
        self.async_write_ha_state()

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.mode.supports_operation_mode:
            return PRESET_MODES.get(self._device.mode.operation_mode.value, PRESET_AWAY)
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        _presets = [
            PRESET_MODES.get(operation_mode.value)
            for operation_mode in self._device.mode.operation_modes
        ]

        return list(filter(None, _presets))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._device.mode.supports_operation_mode:
            knx_operation_mode = HVACOperationMode(PRESET_MODES_INV.get(preset_mode))
            await self._device.mode.set_operation_mode(knx_operation_mode)
            self.async_write_ha_state()
