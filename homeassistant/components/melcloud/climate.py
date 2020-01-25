"""Platform for climate integration."""
from datetime import timedelta
import logging
from typing import List, Optional

from pymelcloud import Device

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.temperature import convert as convert_temperature

from .const import DOMAIN, HVAC_MODE_LOOKUP, HVAC_MODE_REVERSE_LOOKUP, TEMP_UNIT_LOOKUP

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
):
    """Set up MelCloud device climate based on config_entry."""
    mel_devices = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities(
        [MelCloudClimate(mel_device) for mel_device in mel_devices], True
    )


class MelCloudClimate(ClimateDevice):
    """MELCloud device."""

    def __init__(self, device: Device, name=None):
        """Initialize the climate."""
        self._api = device
        if name is None:
            name = device.name

        self._name = "{} {}".format(name, "HVAC")

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._api.device.serial}-{self._api.device.mac}-climate"

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    async def async_update(self):
        """Update state from MELCloud."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    @property
    def state(self) -> str:
        """Return the current state."""
        return self.hvac_mode

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_UNIT_LOOKUP.get(self._api.device.temp_unit, TEMP_CELSIUS)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        mode = self._api.device.operation_mode
        if not self._api.device.power or mode is None:
            return HVAC_MODE_OFF
        return HVAC_MODE_LOOKUP.get(mode)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._api.device.set({"power": False})
            return

        operation_mode = HVAC_MODE_REVERSE_LOOKUP.get(hvac_mode, None)
        if operation_mode is None:
            raise ValueError(f"Invalid hvac_mode [{hvac_mode}]")

        props = {"operation_mode": operation_mode}
        if self.hvac_mode == HVAC_MODE_OFF:
            props["power"] = True
        await self._api.device.set(props)

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_OFF] + list(
            map(HVAC_MODE_LOOKUP.get, self._api.device.operation_modes())
        )

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._api.device.temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._api.device.target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self._api.device.set(
            {"target_temperature": kwargs.get("temperature", self.target_temperature)}
        )

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return self._api.device.target_temperature_step

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        speed = self._api.device.fan_speed
        if speed is None:
            return None
        return speed.replace("-", " ")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._api.device.set({"fan_speed": fan_mode.replace(" ", "-")})

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        speeds = self._api.device.fan_speeds()
        if speeds is None:
            return None
        return list(map(lambda x: x.replace("-", " "), speeds))

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if not self._api.device.power:
            await self._api.device.set({"power": True})

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if self._api.device.power:
            await self._api.device.set({"power": False})

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FAN_MODE | SUPPORT_TARGET_TEMPERATURE

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        min_value = self._api.device.target_temperature_min
        if min_value is not None:
            return min_value

        return convert_temperature(
            DEFAULT_MIN_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        max_value = self._api.device.target_temperature_max
        if max_value is not None:
            return max_value

        return convert_temperature(
            DEFAULT_MAX_TEMP, TEMP_CELSIUS, self.temperature_unit
        )
