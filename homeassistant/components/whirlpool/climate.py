"""Platform for climate integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from whirlpool.aircon import Aircon, FanSpeed as AirconFanSpeed, Mode as AirconMode
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WhirlpoolData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


AIRCON_MODE_MAP = {
    AirconMode.Cool: HVACMode.COOL,
    AirconMode.Heat: HVACMode.HEAT,
    AirconMode.Fan: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_AIRCON_MODE = {v: k for k, v in AIRCON_MODE_MAP.items()}

AIRCON_FANSPEED_MAP = {
    AirconFanSpeed.Off: FAN_OFF,
    AirconFanSpeed.Auto: FAN_AUTO,
    AirconFanSpeed.Low: FAN_LOW,
    AirconFanSpeed.Medium: FAN_MEDIUM,
    AirconFanSpeed.High: FAN_HIGH,
}

FAN_MODE_TO_AIRCON_FANSPEED = {v: k for k, v in AIRCON_FANSPEED_MAP.items()}

SUPPORTED_FAN_MODES = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW, FAN_OFF]
SUPPORTED_HVAC_MODES = [
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
    HVACMode.OFF,
]
SUPPORTED_MAX_TEMP = 30
SUPPORTED_MIN_TEMP = 16
SUPPORTED_SWING_MODES = [SWING_HORIZONTAL, SWING_OFF]
SUPPORTED_TARGET_TEMPERATURE_STEP = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    whirlpool_data: WhirlpoolData = hass.data[DOMAIN][config_entry.entry_id]

    aircons = [
        AirConEntity(
            hass,
            ac_data["SAID"],
            ac_data["NAME"],
            whirlpool_data.backend_selector,
            whirlpool_data.auth,
            async_get_clientsession(hass),
        )
        for ac_data in whirlpool_data.appliances_manager.aircons
    ]
    async_add_entities(aircons, True)


class AirConEntity(ClimateEntity):
    """Representation of an air conditioner."""

    _attr_fan_modes = SUPPORTED_FAN_MODES
    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_max_temp = SUPPORTED_MAX_TEMP
    _attr_min_temp = SUPPORTED_MIN_TEMP
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_swing_modes = SUPPORTED_SWING_MODES
    _attr_target_temperature_step = SUPPORTED_TARGET_TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        hass: HomeAssistant,
        said: str,
        name: str | None,
        backend_selector: BackendSelector,
        auth: Auth,
        session: ClientSession,
    ) -> None:
        """Initialize the entity."""
        self._aircon = Aircon(backend_selector, auth, said, session)
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, said, hass=hass)
        self._attr_unique_id = said

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, said)},
            name=name if name is not None else said,
            manufacturer="Whirlpool",
            model="Sixth Sense",
        )

    async def async_added_to_hass(self) -> None:
        """Connect aircon to the cloud."""
        self._aircon.register_attr_callback(self.async_write_ha_state)
        await self._aircon.connect()

    async def async_will_remove_from_hass(self) -> None:
        """Close Whrilpool Appliance sockets before removing."""
        self._aircon.unregister_attr_callback(self.async_write_ha_state)
        await self._aircon.disconnect()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._aircon.get_online()

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._aircon.get_current_temp()

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._aircon.get_temp()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._aircon.set_temp(kwargs.get(ATTR_TEMPERATURE))

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._aircon.get_current_humidity()

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        return self._aircon.get_humidity()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._aircon.set_humidity(humidity)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, fan."""
        if not self._aircon.get_power_on():
            return HVACMode.OFF

        mode: AirconMode = self._aircon.get_mode()
        return AIRCON_MODE_MAP.get(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._aircon.set_power_on(False)
            return

        if not (mode := HVAC_MODE_TO_AIRCON_MODE.get(hvac_mode)):
            raise ValueError(f"Invalid hvac mode {hvac_mode}")

        await self._aircon.set_mode(mode)
        if not self._aircon.get_power_on():
            await self._aircon.set_power_on(True)

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        fanspeed = self._aircon.get_fanspeed()
        return AIRCON_FANSPEED_MAP.get(fanspeed, FAN_OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if not (fanspeed := FAN_MODE_TO_AIRCON_FANSPEED.get(fan_mode)):
            raise ValueError(f"Invalid fan mode {fan_mode}")
        await self._aircon.set_fanspeed(fanspeed)

    @property
    def swing_mode(self) -> str:
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._aircon.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target temperature."""
        await self._aircon.set_h_louver_swing(swing_mode == SWING_HORIZONTAL)

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self._aircon.set_power_on(True)

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self._aircon.set_power_on(False)
