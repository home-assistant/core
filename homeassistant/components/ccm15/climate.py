"""Climate device for CCM15 coordinator."""

import logging
from typing import Any, override

from ccm15 import CCM15DeviceState, CCM15SlaveDevice

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRECISION_WHOLE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONST_CMD_FAN_MAP, CONST_CMD_STATE_MAP, DOMAIN
from .coordinator import CCM15ConfigEntry, CCM15Coordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CCM15ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator = config_entry.runtime_data

    ac_data: CCM15DeviceState = coordinator.data
    entities = [
        CCM15Climate(coordinator.get_host(), ac_index, coordinator)
        for ac_index in ac_data.devices
    ]
    async_add_entities(entities)


class CCM15Climate(CoordinatorEntity[CCM15Coordinator], ClimateEntity):
    """Climate device for CCM15 coordinator."""

    _attr_has_entity_name = True
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_name = None

    def __init__(
        self, ac_host: str, ac_index: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        super().__init__(coordinator)
        self._ac_index: int = ac_index
        self._attr_unique_id = f"{ac_host}.{ac_index}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"{ac_host}.{ac_index}"),
            },
            name=f"Midea {ac_index}",
            manufacturer="Midea",
            model="CCM15",
        )

    @property
    def data(self) -> CCM15SlaveDevice | None:
        """Return device data."""
        return self.coordinator.get_ac_data(self._ac_index)

    @property
    @override
    def temperature_unit(self) -> str:
        """Return the unit of measurement reported by the device."""
        if (data := self.data) is not None and not data.is_celsius:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    @override
    def current_temperature(self) -> int | None:
        """Return current temperature."""
        if (data := self.data) is not None:
            return data.temperature
        return None

    @property
    @override
    def target_temperature(self) -> int | None:
        """Return target temperature."""
        if (data := self.data) is not None:
            return data.temperature_setpoint
        return None

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        if (data := self.data) is not None:
            mode = data.ac_mode
            return CONST_CMD_STATE_MAP[mode]
        return None

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        if (data := self.data) is not None:
            mode = data.fan_mode
            return CONST_CMD_FAN_MAP[mode]
        return None

    @property
    @override
    def swing_mode(self) -> str | None:
        """Return swing mode."""
        if (data := self.data) is not None:
            return SWING_ON if data.is_swing_on else SWING_OFF
        return None

    @property
    @override
    def available(self) -> bool:
        """Return the availability of the entity."""
        return super().available and self.data is not None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        if (data := self.data) is not None:
            return {"error_code": data.error_code}
        return {}

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            data = self.data
            assert data is not None
            await self.coordinator.async_set_temperature(
                self._ac_index, data, temperature, kwargs.get(ATTR_HVAC_MODE)
            )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        data = self.data
        assert data is not None
        await self.coordinator.async_set_hvac_mode(self._ac_index, data, hvac_mode)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        data = self.data
        assert data is not None
        await self.coordinator.async_set_fan_mode(self._ac_index, data, fan_mode)

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        data = self.data
        assert data is not None
        await self.coordinator.async_set_swing_mode(self._ac_index, data, swing_mode)

    @override
    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @override
    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)
