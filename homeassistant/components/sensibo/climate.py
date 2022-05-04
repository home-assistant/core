"""Support for Sensibo wifi-enabled home thermostats."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_STATE,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.temperature import convert as convert_temperature

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

SERVICE_ASSUME_STATE = "assume_state"

FIELD_TO_FLAG = {
    "fanLevel": ClimateEntityFeature.FAN_MODE,
    "swing": ClimateEntityFeature.SWING_MODE,
    "targetTemperature": ClimateEntityFeature.TARGET_TEMPERATURE,
}

SENSIBO_TO_HA = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "fan": HVACMode.FAN_ONLY,
    "auto": HVACMode.HEAT_COOL,
    "dry": HVACMode.DRY,
    "off": HVACMode.OFF,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}

AC_STATE_TO_DATA = {
    "targetTemperature": "target_temp",
    "fanLevel": "fan_mode",
    "on": "device_on",
    "mode": "hvac_mode",
    "swing": "swing_mode",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sensibo climate entry."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SensiboClimate(coordinator, device_id)
        for device_id, device_data in coordinator.data.parsed.items()
    ]

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ASSUME_STATE,
        {
            vol.Required(ATTR_STATE): vol.In(["on", "off"]),
        },
        "async_assume_state",
    )


class SensiboClimate(SensiboDeviceBaseEntity, ClimateEntity):
    """Representation of a Sensibo device."""

    def __init__(
        self, coordinator: SensiboDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initiate SensiboClimate."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        self._attr_name = self.device_data.name
        self._attr_temperature_unit = (
            TEMP_CELSIUS if self.device_data.temp_unit == "C" else TEMP_FAHRENHEIT
        )
        self._attr_supported_features = self.get_features()
        self._attr_precision = PRECISION_TENTHS

    def get_features(self) -> int:
        """Get supported features."""
        features = 0
        for key in self.device_data.full_features:
            if key in FIELD_TO_FLAG:
                features |= FIELD_TO_FLAG[key]
        return features

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.device_data.humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation."""
        if self.device_data.device_on:
            return SENSIBO_TO_HA[self.device_data.hvac_mode]
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [SENSIBO_TO_HA[mode] for mode in self.device_data.hvac_modes]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return convert_temperature(
            self.device_data.temp,
            TEMP_CELSIUS,
            self.temperature_unit,
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device_data.target_temp

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self.device_data.temp_step

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self.device_data.fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self.device_data.fan_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self.device_data.swing_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self.device_data.swing_modes

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.device_data.temp_list[0]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.device_data.temp_list[-1]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device_data.available and super().available

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if "targetTemperature" not in self.device_data.active_features:
            raise HomeAssistantError(
                "Current mode doesn't support setting Target Temperature"
            )

        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if temperature == self.target_temperature:
            return

        if temperature not in self.device_data.temp_list:
            # Requested temperature is not supported.
            if temperature > self.device_data.temp_list[-1]:
                temperature = self.device_data.temp_list[-1]

            elif temperature < self.device_data.temp_list[0]:
                temperature = self.device_data.temp_list[0]

            else:
                return

        await self._async_set_ac_state_property("targetTemperature", int(temperature))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if "fanLevel" not in self.device_data.active_features:
            raise HomeAssistantError("Current mode doesn't support setting Fanlevel")

        await self._async_set_ac_state_property("fanLevel", fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_set_ac_state_property("on", False)
            return

        # Turn on if not currently on.
        if not self.device_data.device_on:
            await self._async_set_ac_state_property("on", True)

        await self._async_set_ac_state_property("mode", HA_TO_SENSIBO[hvac_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if "swing" not in self.device_data.active_features:
            raise HomeAssistantError("Current mode doesn't support setting Swing")

        await self._async_set_ac_state_property("swing", swing_mode)

    async def async_turn_on(self) -> None:
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", True)

    async def async_turn_off(self) -> None:
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", False)

    async def _async_set_ac_state_property(
        self, name: str, value: str | int | bool, assumed_state: bool = False
    ) -> None:
        """Set AC state."""
        params = {
            "name": name,
            "value": value,
            "ac_states": self.device_data.ac_states,
            "assumed_state": assumed_state,
        }
        result = await self.async_send_command("set_ac_state", params)

        if result["result"]["status"] == "Success":
            setattr(self.device_data, AC_STATE_TO_DATA[name], value)
            self.async_write_ha_state()
            return

        failure = result["result"]["failureReason"]
        raise HomeAssistantError(
            f"Could not set state for device {self.name} due to reason {failure}"
        )

    async def async_assume_state(self, state) -> None:
        """Sync state with api."""
        await self._async_set_ac_state_property("on", state != HVACMode.OFF, True)
        await self.coordinator.async_refresh()
