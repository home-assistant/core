"""Support for Sensibo wifi-enabled home thermostats."""
from __future__ import annotations
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_STATE,
    ATTR_TEMPERATURE,
    CONF_API_KEY,
    CONF_ID,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.temperature import convert as convert_temperature

from .const import ALL, DOMAIN, LOGGER
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboBaseEntity

SERVICE_ASSUME_STATE = "assume_state"
SERVICE_HORIZONTAL_SWING = "horizontal_swing"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
    }
)

FIELD_TO_FLAG = {
    "fanLevel": SUPPORT_FAN_MODE,
    "swing": SUPPORT_SWING_MODE,
    "targetTemperature": SUPPORT_TARGET_TEMPERATURE,
}

SENSIBO_TO_HA = {
    "cool": HVAC_MODE_COOL,
    "heat": HVAC_MODE_HEAT,
    "fan": HVAC_MODE_FAN_ONLY,
    "auto": HVAC_MODE_HEAT_COOL,
    "dry": HVAC_MODE_DRY,
    "off": HVAC_MODE_OFF,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}

AC_STATE_TO_DATA = {
    "targetTemperature": "target_temp",
    "fanLevel": "fan_mode",
    "on": "on",
    "mode": "hvac_mode",
    "swing": "swing_mode",
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Sensibo devices."""
    LOGGER.warning(
        "Loading Sensibo via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sensibo climate entry."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SensiboClimate(coordinator, device_id)
        for device_id, device_data in coordinator.data.parsed.items()
        # Remove none climate devices
        if device_data["hvac_modes"] and device_data["temp"]
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
    platform.async_register_entity_service(
        SERVICE_HORIZONTAL_SWING,
        {
            vol.Required(ATTR_STATE): cv.string,
        },
        "async_set_horizontal_swing",
    )


class SensiboClimate(SensiboBaseEntity, ClimateEntity):
    """Representation of a Sensibo device."""

    def __init__(
        self, coordinator: SensiboDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initiate SensiboClimate."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        self._attr_name = coordinator.data.parsed[device_id]["name"]
        self._attr_temperature_unit = (
            TEMP_CELSIUS
            if coordinator.data.parsed[device_id]["temp_unit"] == "C"
            else TEMP_FAHRENHEIT
        )
        self._attr_supported_features = self.get_features()
        self._attr_precision = PRECISION_TENTHS

    def get_features(self) -> int:
        """Get supported features."""
        features = 0
        for key in self.coordinator.data.parsed[self.unique_id]["full_features"]:
            if key in FIELD_TO_FLAG:
                features |= FIELD_TO_FLAG[key]
        return features

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "horizontal_swing_modes": self.coordinator.data[self.unique_id][
                "horizontal_swing_modes"
            ]
        }

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.coordinator.data.parsed[self.unique_id]["humidity"]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation."""
        return (
            SENSIBO_TO_HA[self.coordinator.data.parsed[self.unique_id]["hvac_mode"]]
            if self.coordinator.data.parsed[self.unique_id]["on"]
            else HVAC_MODE_OFF
        )

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [
            SENSIBO_TO_HA[mode]
            for mode in self.coordinator.data.parsed[self.unique_id]["hvac_modes"]
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return convert_temperature(
            self.coordinator.data.parsed[self.unique_id]["temp"],
            TEMP_CELSIUS,
            self.temperature_unit,
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data.parsed[self.unique_id]["target_temp"]

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self.coordinator.data.parsed[self.unique_id]["temp_step"]

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self.coordinator.data.parsed[self.unique_id]["fan_mode"]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self.coordinator.data.parsed[self.unique_id]["fan_modes"]

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self.coordinator.data.parsed[self.unique_id]["swing_mode"]

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self.coordinator.data.parsed[self.unique_id]["swing_modes"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.coordinator.data.parsed[self.unique_id]["temp_list"][0]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.coordinator.data.parsed[self.unique_id]["temp_list"][-1]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.data.parsed[self.unique_id]["available"]
            and super().available
        )

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (
            "targetTemperature"
            not in self.coordinator.data.parsed[self.unique_id]["active_features"]
        ):
            raise HomeAssistantError(
                "Current mode doesn't support setting Target Temperature"
            )

        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if temperature == self.target_temperature:
            return

        if temperature not in self.coordinator.data.parsed[self.unique_id]["temp_list"]:
            # Requested temperature is not supported.
            if (
                temperature
                > self.coordinator.data.parsed[self.unique_id]["temp_list"][-1]
            ):
                temperature = self.coordinator.data.parsed[self.unique_id]["temp_list"][
                    -1
                ]

            elif (
                temperature
                < self.coordinator.data.parsed[self.unique_id]["temp_list"][0]
            ):
                temperature = self.coordinator.data.parsed[self.unique_id]["temp_list"][
                    0
                ]

            else:
                return

        await self._async_set_ac_state_property("targetTemperature", int(temperature))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if (
            "fanLevel"
            not in self.coordinator.data.parsed[self.unique_id]["active_features"]
        ):
            raise HomeAssistantError("Current mode doesn't support setting Fanlevel")

        await self._async_set_ac_state_property("fanLevel", fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._async_set_ac_state_property("on", False)
            return

        # Turn on if not currently on.
        if not self.coordinator.data.parsed[self.unique_id]["on"]:
            await self._async_set_ac_state_property("on", True)

        await self._async_set_ac_state_property("mode", HA_TO_SENSIBO[hvac_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if (
            "swing"
            not in self.coordinator.data.parsed[self.unique_id]["active_features"]
        ):
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
            "ac_states": self.coordinator.data.parsed[self.unique_id]["ac_states"],
            "assumed_state": assumed_state,
        }
        result = await self.async_send_command("set_ac_state", params)

        if result["result"]["status"] == "Success":
            self.coordinator.data.parsed[self.unique_id][AC_STATE_TO_DATA[name]] = value
            self.async_write_ha_state()
            return

        failure = result["result"]["failureReason"]
        raise HomeAssistantError(
            f"Could not set state for device {self.name} due to reason {failure}"
        )

    async def async_assume_state(self, state) -> None:
        """Sync state with api."""
        await self._async_set_ac_state_property("on", state != HVAC_MODE_OFF, True)
        await self.coordinator.async_refresh()

    async def async_set_horizontal_swing(self, state) -> None:
        """Set new target swing operation."""
        if (
            "horizontalSwing"
            not in self.coordinator.data[self.unique_id]["active_features"]
        ):
            raise HomeAssistantError(
                "Current mode doesn't support setting horizontal swing"
            )

        await self._async_set_ac_state_property("horizontalSwing", state)
