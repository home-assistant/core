"""The Flexit Nordic (BACnet) integration."""
from typing import Any

from flexit_bacnet import VENTILATION_MODE, VENTILATION_MODES, FlexitBACnet

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Flexit Nordic unit."""
    device: FlexitBACnet = hass.data[DOMAIN][config["entry_id"]]

    async_add_entities([FlexitClimateEntity(device)])


class FlexitClimateEntity(ClimateEntity):
    """Flexit air handling unit."""

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.AUX_HEAT
    )

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
    ]

    _attr_preset_modes = [
        PRESET_AWAY,
        PRESET_HOME,
        PRESET_BOOST,
    ]

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_has_entity_name = True
    _attr_icon = "mdi:hvac"

    def __init__(self, device: FlexitBACnet) -> None:
        """Initialize the unit."""
        self._device = device
        self._attr_unique_id = f"{DOMAIN}.{device.serial_number}"

    async def async_update(self) -> None:
        """Refresh unit state."""
        await self._device.update()

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"Flexit Nordic: {self._device.serial_number}"

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self._device.room_temperature)

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self._device.ventilation_mode == VENTILATION_MODES[VENTILATION_MODE.AWAY]:
            return float(self._device.air_temp_setpoint_away)

        return float(self._device.air_temp_setpoint_home)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self._device.ventilation_mode == VENTILATION_MODES[VENTILATION_MODE.AWAY]:
            await self._device.set_air_temp_setpoint_away(temperature)
        else:
            await self._device.set_air_temp_setpoint_home(temperature)

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return {
            VENTILATION_MODES[VENTILATION_MODE.STOP]: PRESET_NONE,
            VENTILATION_MODES[VENTILATION_MODE.AWAY]: PRESET_AWAY,
            VENTILATION_MODES[VENTILATION_MODE.HOME]: PRESET_HOME,
            VENTILATION_MODES[VENTILATION_MODE.HIGH]: PRESET_BOOST,
        }[self._device.ventilation_mode]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        ventilation_mode = {
            PRESET_NONE: VENTILATION_MODE.STOP,
            PRESET_AWAY: VENTILATION_MODE.AWAY,
            PRESET_HOME: VENTILATION_MODE.HOME,
            PRESET_BOOST: VENTILATION_MODE.HIGH,
        }[preset_mode]

        await self._device.set_ventilation_mode(ventilation_mode)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self._device.ventilation_mode == VENTILATION_MODES[VENTILATION_MODE.STOP]:
            return HVACMode.OFF

        if self.is_aux_heat:
            return HVACMode.HEAT

        return HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._device.set_ventilation_mode(VENTILATION_MODE.STOP)
        else:
            await self._device.set_ventilation_mode(VENTILATION_MODE.HOME)

        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_aux_heat_on()
        else:
            await self.async_turn_aux_heat_off()

    @property
    def is_aux_heat(self) -> bool:
        """Return true if aux heater.

        Requires ClimateEntityFeature.AUX_HEAT.
        """
        return bool(self._device.electric_heater)

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        await self._device.enable_electric_heater()

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        await self._device.disable_electric_heater()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "air_filter_operating_time": self._device.air_filter_operating_time,
            "air_filter_polluted": self._device.air_filter_polluted,
            "heat_exchanger_speed": self._device.heat_exchanger_speed,
            "outside_air_temperature": self._device.outside_air_temperature,
            "supply_air_temperature": self._device.supply_air_temperature,
            "extract_air_temperature": self._device.extract_air_temperature,
            "exhaust_air_temperature": self._device.exhaust_air_temperature,
            "electric_heater_power": self._device.electric_heater_power,
            "room_1_humidity": self._device.room_1_humidity,
            "room_2_humidity": self._device.room_2_humidity,
            "room_3_humidity": self._device.room_3_humidity,
        }
