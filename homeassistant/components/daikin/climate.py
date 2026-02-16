"""Support for the Daikin HVAC."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from pydaikin.daikin_base import Appliance

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_STATE_OFF,
    ATTR_STATE_ON,
    ATTR_TARGET_TEMPERATURE,
    DOMAIN,
    ZONE_NAME_UNCONFIGURED,
)
from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .entity import DaikinEntity

_LOGGER = logging.getLogger(__name__)

type DaikinZone = Sequence[str | int]

DAIKIN_ZONE_TEMP_HEAT = "lztemp_h"
DAIKIN_ZONE_TEMP_COOL = "lztemp_c"


HA_STATE_TO_DAIKIN = {
    HVACMode.FAN_ONLY: "fan",
    HVACMode.DRY: "dry",
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "hot",
    HVACMode.HEAT_COOL: "auto",
    HVACMode.OFF: "off",
}

DAIKIN_TO_HA_STATE = {
    "fan": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "cool": HVACMode.COOL,
    "hot": HVACMode.HEAT,
    "auto": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
}

HA_STATE_TO_CURRENT_HVAC = {
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.OFF: HVACAction.OFF,
}

HA_PRESET_TO_DAIKIN = {
    PRESET_AWAY: "on",
    PRESET_NONE: "off",
    PRESET_BOOST: "powerful",
    PRESET_ECO: "econo",
}

HA_ATTR_TO_DAIKIN = {
    ATTR_PRESET_MODE: "en_hol",
    ATTR_HVAC_MODE: "mode",
    ATTR_FAN_MODE: "f_rate",
    ATTR_SWING_MODE: "f_dir",
    ATTR_INSIDE_TEMPERATURE: "htemp",
    ATTR_OUTSIDE_TEMPERATURE: "otemp",
    ATTR_TARGET_TEMPERATURE: "stemp",
}

DAIKIN_ATTR_ADVANCED = "adv"
ZONE_TEMPERATURE_WINDOW = 2


def _zone_error(
    translation_key: str, placeholders: dict[str, str] | None = None
) -> HomeAssistantError:
    """Return a Home Assistant error with Daikin translation info."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


def _zone_is_configured(zone: DaikinZone) -> bool:
    """Return True if the Daikin zone represents a configured zone."""
    if not zone:
        return False
    return zone[0] != ZONE_NAME_UNCONFIGURED


def _zone_temperature_lists(device: Appliance) -> tuple[list[str], list[str]]:
    """Return the decoded zone temperature lists."""
    try:
        heating = device.represent(DAIKIN_ZONE_TEMP_HEAT)[1]
        cooling = device.represent(DAIKIN_ZONE_TEMP_COOL)[1]
    except AttributeError:
        return ([], [])
    return (list(heating or []), list(cooling or []))


def _supports_zone_temperature_control(device: Appliance) -> bool:
    """Return True if the device exposes zone temperature settings."""
    zones = device.zones
    if not zones:
        return False
    heating, cooling = _zone_temperature_lists(device)
    return bool(
        heating
        and cooling
        and len(heating) >= len(zones)
        and len(cooling) >= len(zones)
    )


def _system_target_temperature(device: Appliance) -> float | None:
    """Return the system target temperature when available."""
    target = device.target_temperature
    if target is None:
        return None
    try:
        return float(target)
    except TypeError, ValueError:
        return None


def _zone_temperature_from_list(values: list[str], zone_id: int) -> float | None:
    """Return the parsed temperature for a zone from a Daikin list."""
    if zone_id >= len(values):
        return None
    try:
        return float(values[zone_id])
    except TypeError, ValueError:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on config_entry."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = [DaikinClimate(coordinator)]
    if _supports_zone_temperature_control(coordinator.device):
        zones = coordinator.device.zones or []
        entities.extend(
            DaikinZoneClimate(coordinator, zone_id)
            for zone_id, zone in enumerate(zones)
            if _zone_is_configured(zone)
        )
    async_add_entities(entities)


def format_target_temperature(target_temperature: float) -> str:
    """Format target temperature to be sent to the Daikin unit, rounding to nearest half degree."""
    return str(round(float(target_temperature) * 2, 0) / 2).rstrip("0").rstrip(".")


class DaikinClimate(DaikinEntity, ClimateEntity):
    """Representation of a Daikin HVAC."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = list(HA_STATE_TO_DAIKIN)
    _attr_target_temperature_step = 1
    _attr_fan_modes: list[str]
    _attr_swing_modes: list[str]

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._attr_fan_modes = self.device.fan_rate
        self._attr_swing_modes = self.device.swing_modes
        self._list: dict[str, list[Any]] = {
            ATTR_HVAC_MODE: self._attr_hvac_modes,
            ATTR_FAN_MODE: self._attr_fan_modes,
            ATTR_SWING_MODE: self._attr_swing_modes,
        }

        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
        )

        if self.device.support_away_mode or self.device.support_advanced_modes:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        if self.device.support_fan_rate:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if self.device.support_swing_mode:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

    async def _set(self, settings: dict[str, Any]) -> None:
        """Set device settings using API."""
        values: dict[str, Any] = {}

        for attr in (ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_SWING_MODE, ATTR_HVAC_MODE):
            if (value := settings.get(attr)) is None:
                continue

            if (daikin_attr := HA_ATTR_TO_DAIKIN.get(attr)) is not None:
                if attr == ATTR_HVAC_MODE:
                    values[daikin_attr] = HA_STATE_TO_DAIKIN[value]
                elif value in self._list[attr]:
                    values[daikin_attr] = value.lower()
                else:
                    _LOGGER.error("Invalid value %s for %s", attr, value)

            # temperature
            elif attr == ATTR_TEMPERATURE:
                try:
                    values[HA_ATTR_TO_DAIKIN[ATTR_TARGET_TEMPERATURE]] = (
                        format_target_temperature(value)
                    )
                except ValueError:
                    _LOGGER.error("Invalid temperature %s", value)

        if values:
            await self.device.set(values)
            await self.coordinator.async_refresh()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.device.mac

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.inside_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device.target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._set(kwargs)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current state."""
        ret = HA_STATE_TO_CURRENT_HVAC.get(self.hvac_mode)
        if (
            ret in (HVACAction.COOLING, HVACAction.HEATING)
            and self.device.support_compressor_frequency
            and self.device.compressor_frequency == 0
        ):
            return HVACAction.IDLE
        return ret

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        daikin_mode = self.device.represent(HA_ATTR_TO_DAIKIN[ATTR_HVAC_MODE])[1]
        return DAIKIN_TO_HA_STATE.get(daikin_mode, HVACMode.HEAT_COOL)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self._set({ATTR_HVAC_MODE: hvac_mode})

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        return self.device.represent(HA_ATTR_TO_DAIKIN[ATTR_FAN_MODE])[1].title()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self._set({ATTR_FAN_MODE: fan_mode})

    @property
    def swing_mode(self) -> str:
        """Return the fan setting."""
        return self.device.represent(HA_ATTR_TO_DAIKIN[ATTR_SWING_MODE])[1].title()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target temperature."""
        await self._set({ATTR_SWING_MODE: swing_mode})

    @property
    def preset_mode(self) -> str:
        """Return the preset_mode."""
        if (
            self.device.represent(HA_ATTR_TO_DAIKIN[ATTR_PRESET_MODE])[1]
            == HA_PRESET_TO_DAIKIN[PRESET_AWAY]
        ):
            return PRESET_AWAY
        if (
            HA_PRESET_TO_DAIKIN[PRESET_BOOST]
            in self.device.represent(DAIKIN_ATTR_ADVANCED)[1]
        ):
            return PRESET_BOOST
        if (
            HA_PRESET_TO_DAIKIN[PRESET_ECO]
            in self.device.represent(DAIKIN_ATTR_ADVANCED)[1]
        ):
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode == PRESET_AWAY:
            await self.device.set_holiday(ATTR_STATE_ON)
        elif preset_mode == PRESET_BOOST:
            await self.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_BOOST], ATTR_STATE_ON
            )
        elif preset_mode == PRESET_ECO:
            await self.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_ECO], ATTR_STATE_ON
            )
        elif self.preset_mode == PRESET_AWAY:
            await self.device.set_holiday(ATTR_STATE_OFF)
        elif self.preset_mode == PRESET_BOOST:
            await self.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_BOOST], ATTR_STATE_OFF
            )
        elif self.preset_mode == PRESET_ECO:
            await self.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_ECO], ATTR_STATE_OFF
            )
        await self.coordinator.async_refresh()

    @property
    def preset_modes(self) -> list[str]:
        """List of available preset modes."""
        ret = [PRESET_NONE]
        if self.device.support_away_mode:
            ret.append(PRESET_AWAY)
        if self.device.support_advanced_modes:
            ret += [PRESET_ECO, PRESET_BOOST]
        return ret

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self.device.set({})
        await self.coordinator.async_refresh()

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self.device.set(
            {HA_ATTR_TO_DAIKIN[ATTR_HVAC_MODE]: HA_STATE_TO_DAIKIN[HVACMode.OFF]}
        )
        await self.coordinator.async_refresh()


class DaikinZoneClimate(DaikinEntity, ClimateEntity):
    """Representation of a Daikin zone temperature controller."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: DaikinCoordinator, zone_id: int) -> None:
        """Initialize the zone climate entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{self.device.mac}-zone{zone_id}-temperature"
        zone_name = self.device.zones[self._zone_id][0]
        self._attr_name = f"{zone_name} temperature"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the hvac modes (mirrors the main unit)."""
        return [self.hvac_mode]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        daikin_mode = self.device.represent(HA_ATTR_TO_DAIKIN[ATTR_HVAC_MODE])[1]
        return DAIKIN_TO_HA_STATE.get(daikin_mode, HVACMode.HEAT_COOL)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return HA_STATE_TO_CURRENT_HVAC.get(self.hvac_mode)

    @property
    def target_temperature(self) -> float | None:
        """Return the zone target temperature for the active mode."""
        heating, cooling = _zone_temperature_lists(self.device)
        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return _zone_temperature_from_list(heating, self._zone_id)
        if mode == HVACMode.COOL:
            return _zone_temperature_from_list(cooling, self._zone_id)
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum selectable temperature."""
        target = _system_target_temperature(self.device)
        if target is None:
            return super().min_temp
        return target - ZONE_TEMPERATURE_WINDOW

    @property
    def max_temp(self) -> float:
        """Return the maximum selectable temperature."""
        target = _system_target_temperature(self.device)
        if target is None:
            return super().max_temp
        return target + ZONE_TEMPERATURE_WINDOW

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and _supports_zone_temperature_control(self.device)
            and _system_target_temperature(self.device) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional metadata."""
        return {"zone_id": self._zone_id}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the zone temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="zone_temperature_missing",
            )
        zones = self.device.zones
        if not zones or not _supports_zone_temperature_control(self.device):
            raise _zone_error("zone_parameters_unavailable")

        try:
            zone = zones[self._zone_id]
        except (IndexError, TypeError) as err:
            raise _zone_error(
                "zone_missing",
                {
                    "zone_id": str(self._zone_id),
                    "max_zone": str(len(zones) - 1),
                },
            ) from err

        if not _zone_is_configured(zone):
            raise _zone_error("zone_inactive", {"zone_id": str(self._zone_id)})

        temperature_value = float(temperature)
        target = _system_target_temperature(self.device)
        if target is None:
            raise _zone_error("zone_parameters_unavailable")

        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            zone_key = DAIKIN_ZONE_TEMP_HEAT
        elif mode == HVACMode.COOL:
            zone_key = DAIKIN_ZONE_TEMP_COOL
        else:
            raise _zone_error("zone_hvac_mode_unsupported")

        zone_value = str(round(temperature_value))
        try:
            await self.device.set_zone(self._zone_id, zone_key, zone_value)
        except (AttributeError, KeyError, NotImplementedError, TypeError) as err:
            raise _zone_error("zone_set_failed") from err

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Disallow changing HVAC mode via zone climate."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="zone_hvac_read_only",
        )
