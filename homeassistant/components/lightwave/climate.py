"""Support for LightwaveRF TRVs."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_SERIAL, LIGHTWAVE_LINK


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return LightWave lights."""
    if discovery_info is None:
        return

    entities = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        serial = device_config[CONF_SERIAL]
        entities.append(LightwaveTrv(name, device_id, lwlink, serial))

    async_add_entities(entities)


class LightwaveTrv(ClimateEntity):
    """Representation of a LightWaveRF TRV."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, name, device_id, lwlink, serial):
        """Initialize LightwaveTrv entity."""
        self._attr_name = name
        self._device_id = device_id
        self._lwlink = lwlink
        self._serial = serial
        self._attr_unique_id = f"{serial}-trv"
        # inhibit is used to prevent race condition on update.  If non zero, skip next update cycle.
        self._inhibit = 0

    def update(self) -> None:
        """Communicate with a Lightwave RTF Proxy to get state."""
        (temp, targ, _, trv_output) = self._lwlink.read_trv_status(self._serial)
        if temp is not None:
            self._attr_current_temperature = temp
        if targ is not None:
            if self._inhibit == 0:
                self._attr_target_temperature = targ
                if targ == 0:
                    # TRV off
                    self._attr_target_temperature = None
                if targ >= 40:
                    # Call for heat mode, or TRV in a fixed position
                    self._attr_target_temperature = None
            else:
                # Done the job - use proxy next iteration
                self._inhibit = 0
        if trv_output is not None:
            if trv_output > 0:
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_hvac_action = HVACAction.OFF

    @property
    def target_temperature(self):
        """Target room temperature."""
        if self._inhibit > 0:
            # If we get an update before the new temp has
            # propagated, the target temp is set back to the
            # old target on the next poll, showing a false
            # reading temporarily.
            self._attr_target_temperature = self._inhibit
        return self._attr_target_temperature

    def set_temperature(self, **kwargs: Any) -> None:
        """Set TRV target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            self._inhibit = self._attr_target_temperature
        self._lwlink.set_temperature(
            self._device_id, self._attr_target_temperature, self._attr_name
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC Mode for TRV."""
