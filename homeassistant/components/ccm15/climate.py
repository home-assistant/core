"""Climate device for CCM15 coordinator."""
import logging
from typing import Any

from ccm15 import CCM15DeviceState

from homeassistant.components.climate import (
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONST_CMD_FAN_MAP, CONST_CMD_STATE_MAP, DOMAIN
from .coordinator import CCM15Coordinator

_LOGGER = logging.getLogger(__name__)


class CCM15Climate(CoordinatorEntity[CCM15Coordinator], ClimateEntity):
    """Climate device for CCM15 coordinator."""

    def __init__(
        self, ac_host: str, ac_index: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        super().__init__(coordinator)
        self._ac_host: str = ac_host
        self._ac_index: int = ac_index
        self._attr_should_poll = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_has_entity_name = True
        self._attr_name = f"{self._ac_index}"
        self._attr_target_temperature_step = PRECISION_WHOLE
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.AUTO,
        ]
        self._attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_swing_modes = [SWING_OFF, SWING_ON]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{self._ac_host}.{self._ac_index}"

    @property
    def current_temperature(self) -> int | None:
        """Return current temperature."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            _LOGGER.debug("temp[%s]=%s", self._ac_index, data.temperature)
            return data.temperature
        return None

    @property
    def target_temperature(self) -> int | None:
        """Return target temperature."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            _LOGGER.debug("set_temp[%s]=%s", self._ac_index, data.temperature_setpoint)
            return data.temperature_setpoint
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            mode = data.ac_mode
            _LOGGER.debug("hvac_mode[%s]=%s", self._ac_index, mode)
            return CONST_CMD_STATE_MAP[mode]
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            mode = data.fan_mode
            _LOGGER.debug("fan_mode[%s]=%s", self._ac_index, mode)
            return CONST_CMD_FAN_MAP[mode]
        return None

    @property
    def swing_mode(self) -> str | None:
        """Return swing mode."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            _LOGGER.debug("is_swing_on[%s]=%s", self._ac_index, data.is_swing_on)
            return SWING_ON if data.is_swing_on else SWING_OFF
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"{self._ac_host}.{self._ac_index}"),
            },
            name=self._attr_name,
            manufacturer="Midea",
            model="CCM15",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        if data := self.coordinator.get_ac_data(self._ac_index):
            return {"error_code": data.error_code}
        return {}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_set_temperature(self._ac_index, temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        await self.coordinator.async_set_hvac_mode(self._ac_index, hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self.coordinator.async_set_fan_mode(self._ac_index, fan_mode)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator: CCM15Coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    ac_index = 0
    ac_data: CCM15DeviceState = coordinator.data
    for ac_index in ac_data.devices:
        _LOGGER.debug("Creating new ac device at index '%s'", ac_index)
        ac_device = CCM15Climate(coordinator.get_host(), ac_index, coordinator)
        entities.append(ac_device)
    async_add_entities(entities, True)
