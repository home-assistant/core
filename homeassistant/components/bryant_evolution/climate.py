"""Support for Bryant Evolution HVAC systems."""

from datetime import timedelta
import logging
from typing import Any

from evolutionhttp import BryantEvolutionClient

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SYSTEM_ID, CONF_ZONE_ID

_LOGGER = logging.getLogger(__name__)

type BryantEvolutionConfigEntry = ConfigEntry[BryantEvolutionClient]  # noqa: F821
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BryantEvolutionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]
    system_id = config_entry.data[CONF_SYSTEM_ID]
    zone_id = config_entry.data[CONF_ZONE_ID]
    client = config_entry.runtime_data
    climate = BryantEvolutionClimate(host, system_id, zone_id, client)
    async_add_entities([climate], update_before_add=True)


class BryantEvolutionClimate(ClimateEntity):
    """ClimateEntity for Bryant Evolution HVAC systems."""

    def __init__(
        self: ClimateEntity,
        host: str,
        system_id: int,
        zone_id: int,
        client: BryantEvolutionClient,
    ) -> None:
        """Initialize an entity from parts."""
        self._host = host
        self._system_id = system_id
        self._zone_id = zone_id
        self._client = client
        self._name = f"Bryant Evolution (System {system_id}, Zone {zone_id})"
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None
        self._attr_hvac_mode = None
        self._attr_fan_mode = None
        self._attr_hvac_action = None
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_hvac_action = None
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    async def async_update(self) -> None:
        """Update the entity state."""
        self._attr_current_temperature = await self._client.read_current_temperature()
        self._attr_fan_mode = await self._client.read_fan_mode()

        self._attr_target_temperature = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_hvac_mode = await self._read_hvac_mode()

        # Set target_temperature or target_temperature_{high, low} based on mode.
        match self._attr_hvac_mode:
            case HVACMode.HEAT:
                self._attr_target_temperature = (
                    await self._client.read_heating_setpoint()
                )
            case HVACMode.COOL:
                self._attr_target_temperature = (
                    await self._client.read_cooling_setpoint()
                )
            case HVACMode.HEAT_COOL:
                self._attr_target_temperature_high = (
                    await self._client.read_cooling_setpoint()
                )
                self._attr_target_temperature_low = (
                    await self._client.read_heating_setpoint()
                )
            case HVACMode.OFF:
                pass
            case _:
                _LOGGER.error("Unknown HVAC mode %s", self._attr_hvac_mode)

        # Note: depends on current temperature and target temperature low read
        # above.
        self._attr_hvac_action = await self._read_hvac_action()
        _LOGGER.error("XXX async update done")

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"bryant_evolution_{self._host}_{self._system_id}_{self._zone_id}"

    async def _read_hvac_mode(self) -> HVACMode:
        mode_and_active = await self._client.read_hvac_mode()
        if not mode_and_active:
            raise HomeAssistantError("Failed to read current HVAC mode")
        mode = mode_and_active[0]

        # Response format is MODE and (optionally) a number indicating which
        # system is currently calling for the MODE (e.g., HEAT 1 if system 1
        # is calling for heat; HEAT if no call is being made).
        match mode.upper():
            case "HEAT":
                return HVACMode.HEAT
            case "COOL":
                return HVACMode.COOL
            case "AUTO":
                return HVACMode.HEAT_COOL
            case "OFF":
                return HVACMode.OFF

        raise HomeAssistantError(f"Cannot parse response to HVACMode: {mode}")

    async def _read_hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        mode_and_active = await self._client.read_hvac_mode()
        if not mode_and_active:
            raise HomeAssistantError("Failed to read current HVAC action")
        mode, is_active = mode_and_active
        if not is_active:
            return HVACAction.OFF
        match mode.upper():
            case "HEAT":
                return HVACAction.HEATING
            case "COOL":
                return HVACAction.COOLING
            case "OFF":
                return HVACAction.OFF
            case "AUTO":
                # In AUTO, we need to figure out what the actual mode is
                # based on the setpoints.
                if (
                    self.current_temperature is not None
                    and self.target_temperature_low is not None
                ):
                    if self.current_temperature > self.target_temperature_low:
                        # If the system is on and the current temperature is
                        # higher than the point at which heating would activate,
                        # then we must be cooling.
                        return HVACAction.COOLING
                    return HVACAction.HEATING
        raise HomeAssistantError(
            f"Could not determine HVAC action: {mode_and_active}, {self.current_temperature}, {self.target_temperature_low}"
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT_COOL:
            hvac_mode = HVACMode.AUTO
        if not await self._client.set_hvac_mode(hvac_mode):
            raise HomeAssistantError("Failed to set HVAC mode")
        self._attr_hvac_mode = hvac_mode
        self._async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get("target_temp_high"):
            temp = int(kwargs["target_temp_high"])
            if not await self._client.set_cooling_setpoint(temp):
                raise HomeAssistantError("Failed to set cooling setpoint")
            self._attr_target_temperature_high = temp
            self._async_write_ha_state()

        if kwargs.get("target_temp_low"):
            temp = int(kwargs["target_temp_low"])
            if not await self._client.set_heating_setpoint(temp):
                raise HomeAssistantError("Failed to set heating setpoint")
            self._attr_target_temperature_low = temp
            self._async_write_ha_state()

        if kwargs.get("temperature"):
            temp = int(kwargs["temperature"])
            fn = (
                self._client.set_heating_setpoint
                if self.hvac_mode == HVACMode.HEAT
                else self._client.set_cooling_setpoint
            )
            if not await fn(temp):
                raise HomeAssistantError("Failed to set temperature")
            self._attr_target_temperature = temp
            self._async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not await self._client.set_fan_mode(fan_mode):
            raise HomeAssistantError("Failed to set fan mode")
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC operation modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL, HVACMode.OFF]

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return ["AUTO", "LOW", "MED", "HIGH"]
