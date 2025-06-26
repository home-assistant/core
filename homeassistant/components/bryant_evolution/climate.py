"""Support for Bryant Evolution HVAC systems."""

from datetime import timedelta
import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BryantEvolutionConfigEntry, names
from .const import CONF_SYSTEM_ZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BryantEvolutionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a config entry."""

    # Add a climate entity for each system/zone.
    sam_uid = names.sam_device_uid(config_entry)
    entities: list[Entity] = []
    for sz in config_entry.data[CONF_SYSTEM_ZONE]:
        system_id = sz[0]
        zone_id = sz[1]
        client = config_entry.runtime_data.get(tuple(sz))
        climate = BryantEvolutionClimate(
            client,
            system_id,
            zone_id,
            sam_uid,
        )
        entities.append(climate)
    async_add_entities(entities, update_before_add=True)


class BryantEvolutionClimate(ClimateEntity):
    """ClimateEntity for Bryant Evolution HVAC systems.

    Design note: this class updates using polling. However, polling
    is very slow (~1500 ms / parameter). To improve the user
    experience on updates, we also locally update this instance and
    call async_write_ha_state as well.
    """

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    ]
    _attr_fan_modes = ["auto", "low", "med", "high"]

    def __init__(
        self,
        client: BryantEvolutionLocalClient,
        system_id: int,
        zone_id: int,
        sam_uid: str,
    ) -> None:
        """Initialize an entity from parts."""
        self._client = client
        self._attr_name = None
        self._attr_unique_id = names.zone_entity_uid(sam_uid, system_id, zone_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Bryant",
            via_device=(DOMAIN, names.system_device_uid(sam_uid, system_id)),
            name=f"System {system_id} Zone {zone_id}",
        )

    async def async_update(self) -> None:
        """Update the entity state."""
        self._attr_current_temperature = await self._client.read_current_temperature()
        if (fan_mode := await self._client.read_fan_mode()) is not None:
            self._attr_fan_mode = fan_mode.lower()
        else:
            self._attr_fan_mode = None
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

    async def _read_hvac_mode(self) -> HVACMode:
        mode_and_active = await self._client.read_hvac_mode()
        if not mode_and_active:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_read_hvac_mode"
            )
        mode = mode_and_active[0]
        mode_enum = {
            "HEAT": HVACMode.HEAT,
            "COOL": HVACMode.COOL,
            "AUTO": HVACMode.HEAT_COOL,
            "OFF": HVACMode.OFF,
        }.get(mode.upper())
        if mode_enum is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_parse_hvac_mode",
                translation_placeholders={"mode": mode},
            )
        return mode_enum

    async def _read_hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        mode_and_active = await self._client.read_hvac_mode()
        if not mode_and_active:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_read_hvac_action"
            )
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
                # In AUTO, we need to figure out what the actual action is
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
            translation_domain=DOMAIN,
            translation_key="failed_to_parse_hvac_mode",
            translation_placeholders={
                "mode_and_active": mode_and_active,
                "current_temperature": str(self.current_temperature),
                "target_temperature_low": str(self.target_temperature_low),
            },
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT_COOL:
            hvac_mode = HVACMode.AUTO
        if not await self._client.set_hvac_mode(hvac_mode):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_set_hvac_mode"
            )
        self._attr_hvac_mode = hvac_mode
        self._async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get("target_temp_high"):
            temp = int(kwargs["target_temp_high"])
            if not await self._client.set_cooling_setpoint(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_clsp"
                )
            self._attr_target_temperature_high = temp

        if kwargs.get("target_temp_low"):
            temp = int(kwargs["target_temp_low"])
            if not await self._client.set_heating_setpoint(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_htsp"
                )
            self._attr_target_temperature_low = temp

        if kwargs.get("temperature"):
            temp = int(kwargs["temperature"])
            fn = (
                self._client.set_heating_setpoint
                if self.hvac_mode == HVACMode.HEAT
                else self._client.set_cooling_setpoint
            )
            if not await fn(temp):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="failed_to_set_temp"
                )
            self._attr_target_temperature = temp

        # If we get here, we must have changed something unless HA allowed an
        # invalid service call (without any recognized kwarg).
        self._async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not await self._client.set_fan_mode(fan_mode):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="failed_to_set_fan_mode"
            )
        self._attr_fan_mode = fan_mode.lower()
        self.async_write_ha_state()
