"""Support for deCONZ climate devices."""
from __future__ import annotations

from typing import Any

from pydeconz.models.sensor.thermostat import (
    THERMOSTAT_FAN_MODE_AUTO,
    THERMOSTAT_FAN_MODE_HIGH,
    THERMOSTAT_FAN_MODE_LOW,
    THERMOSTAT_FAN_MODE_MEDIUM,
    THERMOSTAT_FAN_MODE_OFF,
    THERMOSTAT_FAN_MODE_ON,
    THERMOSTAT_FAN_MODE_SMART,
    THERMOSTAT_MODE_AUTO,
    THERMOSTAT_MODE_COOL,
    THERMOSTAT_MODE_HEAT,
    THERMOSTAT_MODE_OFF,
    THERMOSTAT_PRESET_AUTO,
    THERMOSTAT_PRESET_BOOST,
    THERMOSTAT_PRESET_COMFORT,
    THERMOSTAT_PRESET_COMPLEX,
    THERMOSTAT_PRESET_ECO,
    THERMOSTAT_PRESET_HOLIDAY,
    THERMOSTAT_PRESET_MANUAL,
    Thermostat,
)

from homeassistant.components.climate import DOMAIN, ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_LOCKED, ATTR_OFFSET, ATTR_VALVE
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_FAN_SMART = "smart"

FAN_MODE_TO_DECONZ = {
    DECONZ_FAN_SMART: THERMOSTAT_FAN_MODE_SMART,
    FAN_AUTO: THERMOSTAT_FAN_MODE_AUTO,
    FAN_HIGH: THERMOSTAT_FAN_MODE_HIGH,
    FAN_MEDIUM: THERMOSTAT_FAN_MODE_MEDIUM,
    FAN_LOW: THERMOSTAT_FAN_MODE_LOW,
    FAN_ON: THERMOSTAT_FAN_MODE_ON,
    FAN_OFF: THERMOSTAT_FAN_MODE_OFF,
}
DECONZ_TO_FAN_MODE = {value: key for key, value in FAN_MODE_TO_DECONZ.items()}

HVAC_MODE_TO_DECONZ: dict[HVACMode, str] = {
    HVACMode.AUTO: THERMOSTAT_MODE_AUTO,
    HVACMode.COOL: THERMOSTAT_MODE_COOL,
    HVACMode.HEAT: THERMOSTAT_MODE_HEAT,
    HVACMode.OFF: THERMOSTAT_MODE_OFF,
}

DECONZ_PRESET_AUTO = "auto"
DECONZ_PRESET_COMPLEX = "complex"
DECONZ_PRESET_HOLIDAY = "holiday"
DECONZ_PRESET_MANUAL = "manual"

PRESET_MODE_TO_DECONZ = {
    DECONZ_PRESET_AUTO: THERMOSTAT_PRESET_AUTO,
    PRESET_BOOST: THERMOSTAT_PRESET_BOOST,
    PRESET_COMFORT: THERMOSTAT_PRESET_COMFORT,
    DECONZ_PRESET_COMPLEX: THERMOSTAT_PRESET_COMPLEX,
    PRESET_ECO: THERMOSTAT_PRESET_ECO,
    DECONZ_PRESET_HOLIDAY: THERMOSTAT_PRESET_HOLIDAY,
    DECONZ_PRESET_MANUAL: THERMOSTAT_PRESET_MANUAL,
}
DECONZ_TO_PRESET_MODE = {value: key for key, value in PRESET_MODE_TO_DECONZ.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ climate devices.

    Thermostats are based on the same device class as sensors in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_climate(sensors: list[Thermostat] | None = None) -> None:
        """Add climate devices from deCONZ."""
        entities: list[DeconzThermostat] = []

        if sensors is None:
            sensors = list(gateway.api.sensors.thermostat.values())

        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if (
                isinstance(sensor, Thermostat)
                and sensor.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzThermostat(sensor, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_sensor,
            async_add_climate,
        )
    )

    async_add_climate()


class DeconzThermostat(DeconzDevice, ClimateEntity):
    """Representation of a deCONZ thermostat."""

    TYPE = DOMAIN
    _device: Thermostat

    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, device: Thermostat, gateway: DeconzGateway) -> None:
        """Set up thermostat device."""
        super().__init__(device, gateway)

        self._attr_hvac_modes = [
            HVACMode.HEAT,
            HVACMode.OFF,
        ]
        if device.mode:
            self._attr_hvac_modes.append(HVACMode.AUTO)

            if "coolsetpoint" in device.raw["config"]:
                self._attr_hvac_modes.append(HVACMode.COOL)

        self._deconz_to_hvac_mode = {
            HVAC_MODE_TO_DECONZ[item]: item for item in self._attr_hvac_modes
        }

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        if device.fan_mode:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = list(FAN_MODE_TO_DECONZ)

        if device.preset:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(PRESET_MODE_TO_DECONZ)

    # Fan control

    @property
    def fan_mode(self) -> str:
        """Return fan operation."""
        if self._device.fan_mode in DECONZ_TO_FAN_MODE:
            return DECONZ_TO_FAN_MODE[self._device.fan_mode]
        return DECONZ_TO_FAN_MODE[FAN_ON if self._device.state_on else FAN_OFF]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in FAN_MODE_TO_DECONZ:
            raise ValueError(f"Unsupported fan mode {fan_mode}")

        await self._device.set_config(fan_mode=FAN_MODE_TO_DECONZ[fan_mode])

    # HVAC control

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._device.mode in self._deconz_to_hvac_mode:
            return self._deconz_to_hvac_mode[self._device.mode]
        return HVACMode.HEAT if self._device.state_on else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self._attr_hvac_modes:
            raise ValueError(f"Unsupported HVAC mode {hvac_mode}")

        if len(self._attr_hvac_modes) == 2:  # Only allow turn on and off thermostat
            await self._device.set_config(on=hvac_mode != HVACMode.OFF)
        else:
            await self._device.set_config(mode=HVAC_MODE_TO_DECONZ[hvac_mode])

    # Preset control

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        if self._device.preset in DECONZ_TO_PRESET_MODE:
            return DECONZ_TO_PRESET_MODE[self._device.preset]
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in PRESET_MODE_TO_DECONZ:
            raise ValueError(f"Unsupported preset mode {preset_mode}")

        await self._device.set_config(preset=PRESET_MODE_TO_DECONZ[preset_mode])

    # Temperature control

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._device.scaled_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self._device.mode == THERMOSTAT_MODE_COOL and self._device.cooling_setpoint:
            return self._device.cooling_setpoint

        if self._device.heating_setpoint:
            return self._device.heating_setpoint

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Expected attribute {ATTR_TEMPERATURE}")

        data = {"heating_setpoint": kwargs[ATTR_TEMPERATURE] * 100}
        if self._device.mode == "cool":
            data = {"cooling_setpoint": kwargs[ATTR_TEMPERATURE] * 100}

        await self._device.set_config(**data)

    @property
    def extra_state_attributes(self) -> dict[str, bool | int]:
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._device.offset is not None:
            attr[ATTR_OFFSET] = self._device.offset

        if self._device.valve is not None:
            attr[ATTR_VALVE] = self._device.valve

        if self._device.locked is not None:
            attr[ATTR_LOCKED] = self._device.locked

        return attr
