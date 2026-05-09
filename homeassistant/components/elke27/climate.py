"""Thermostats for the Elke27 integration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elke27DataUpdateCoordinator
from .entity import build_unique_id, device_info_for_entry, sanitize_name, unique_base

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .hub import Elke27Hub
    from .models import Elke27RuntimeData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_HVAC_TO_TSTAT_MODE: dict[HVACMode, str] = {
    HVACMode.OFF: "OFF",
    HVACMode.HEAT: "HEAT",
    HVACMode.COOL: "COOL",
    HVACMode.HEAT_COOL: "AUTO",
}
_TSTAT_TO_HVAC_MODE: dict[str, HVACMode] = {
    "OFF": HVACMode.OFF,
    "HEAT": HVACMode.HEAT,
    "COOL": HVACMode.COOL,
    "AUTO": HVACMode.HEAT_COOL,
}
_FAN_TO_TSTAT_MODE: dict[str, str] = {
    FAN_AUTO: "AUTO",
    FAN_ON: "ON",
}
_TSTAT_TO_FAN_MODE: dict[str, str] = {
    "AUTO": FAN_AUTO,
    "ON": FAN_ON,
}
_IMPLIED_DECIMAL_TEMP_THRESHOLD = 200


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 thermostats from a config entry."""
    data: Elke27RuntimeData | None = entry.runtime_data
    if data is None:
        _LOGGER.debug("Skipping climate setup because runtime data is missing")
        return
    hub = data.hub
    coordinator = data.coordinator
    known_ids: set[int] = set()

    def _async_add_tstats() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Thermostat entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27Thermostat] = []
        tstats = list(_iter_tstats(snapshot))
        if not tstats:
            _LOGGER.debug("No thermostats available for entity creation")
            return
        for tstat in tstats:
            tstat_id = getattr(tstat, "tstat_id", None)
            if not isinstance(tstat_id, int):
                continue
            if tstat_id in known_ids:
                continue
            known_ids.add(tstat_id)
            entities.append(Elke27Thermostat(coordinator, hub, entry, tstat_id, tstat))
        if entities:
            async_add_entities(entities)

    _async_add_tstats()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_tstats))


class Elke27Thermostat(
    CoordinatorEntity[Elke27DataUpdateCoordinator],
    ClimateEntity,
):
    """Representation of an Elke27 thermostat."""

    _attr_has_entity_name = True
    _attr_translation_key = "thermostat"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE | ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]
    _attr_fan_modes: ClassVar[list[str]] = [FAN_AUTO, FAN_ON]
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 40
    _attr_max_temp = 99

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        tstat_id: int,
        tstat: Any,
    ) -> None:
        """Initialize the thermostat entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._tstat_id = tstat_id
        self._attr_name = (
            sanitize_name(getattr(tstat, "name", None)) or f"Thermostat {tstat_id}"
        )
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "tstat",
            tstat_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_tstat(self.coordinator.data, self._tstat_id) is not None
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        tstat = _get_tstat(self.coordinator.data, self._tstat_id)
        if tstat is None:
            self._log_missing()
            return HVACMode.OFF
        mode = getattr(tstat, "mode", None)
        if isinstance(mode, str):
            normalized = mode.strip().upper()
            return _TSTAT_TO_HVAC_MODE.get(normalized, HVACMode.OFF)
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running HVAC action."""
        mode = self.hvac_mode
        if mode is HVACMode.HEAT:
            return HVACAction.HEATING
        if mode is HVACMode.COOL:
            return HVACAction.COOLING
        if mode is HVACMode.OFF:
            return HVACAction.OFF
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        tstat = _get_tstat(self.coordinator.data, self._tstat_id)
        if tstat is None:
            return None
        temperature = getattr(tstat, "temperature", None)
        return _normalize_temperature(temperature)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the current low setpoint."""
        tstat = _get_tstat(self.coordinator.data, self._tstat_id)
        if tstat is None:
            return None
        heat_setpoint = getattr(tstat, "heat_setpoint", None)
        if isinstance(heat_setpoint, int | float):
            return float(heat_setpoint)
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the current high setpoint."""
        tstat = _get_tstat(self.coordinator.data, self._tstat_id)
        if tstat is None:
            return None
        cool_setpoint = getattr(tstat, "cool_setpoint", None)
        if isinstance(cool_setpoint, int | float):
            return float(cool_setpoint)
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        tstat = _get_tstat(self.coordinator.data, self._tstat_id)
        if tstat is None:
            return None
        fan_mode = getattr(tstat, "fan_mode", None)
        if isinstance(fan_mode, str):
            return _TSTAT_TO_FAN_MODE.get(fan_mode.strip().upper())
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode."""
        mode = _HVAC_TO_TSTAT_MODE.get(hvac_mode)
        if mode is None:
            msg = "HVAC mode is not supported."
            raise HomeAssistantError(msg)
        try:
            await self._hub.async_set_tstat_status(self._tstat_id, mode=mode)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        value = _FAN_TO_TSTAT_MODE.get(fan_mode)
        if value is None:
            msg = "Fan mode is not supported."
            raise HomeAssistantError(msg)
        try:
            await self._hub.async_set_tstat_status(self._tstat_id, fan_mode=value)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperatures."""
        heat_setpoint: int | None = None
        cool_setpoint: int | None = None

        if ATTR_TARGET_TEMP_LOW in kwargs:
            low = kwargs[ATTR_TARGET_TEMP_LOW]
            if isinstance(low, int | float):
                heat_setpoint = round(low)
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            high = kwargs[ATTR_TARGET_TEMP_HIGH]
            if isinstance(high, int | float):
                cool_setpoint = round(high)

        if heat_setpoint is None and cool_setpoint is None:
            msg = "At least one target temperature is required."
            raise HomeAssistantError(msg)

        try:
            await self._hub.async_set_tstat_status(
                self._tstat_id,
                heat_setpoint=heat_setpoint,
                cool_setpoint=cool_setpoint,
            )
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    def _log_missing(self) -> None:
        """Log when the thermostat snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Thermostat %s missing from snapshot", self._tstat_id)


def _iter_tstats(snapshot: Any) -> Iterable[Any]:
    thermostats = getattr(snapshot, "thermostats", None)
    if thermostats is None:
        return []
    if isinstance(thermostats, Mapping):
        return list(thermostats.values())
    if isinstance(thermostats, list | tuple):
        return thermostats
    return []


def _tstat_id_of(tstat: Any) -> int | None:
    tstat_id = getattr(tstat, "tstat_id", None)
    if isinstance(tstat_id, int):
        return tstat_id
    return None


def _get_tstat(snapshot: Any, tstat_id: int) -> Any | None:
    for tstat in _iter_tstats(snapshot):
        entity_id = _tstat_id_of(tstat)
        if entity_id == tstat_id:
            return tstat
    return None


def _normalize_temperature(value: Any) -> float | None:
    """Normalize thermostat temperatures to display units."""
    if not isinstance(value, int | float):
        return None
    # Some panels report temperature with one implied decimal place.
    if abs(value) >= _IMPLIED_DECIMAL_TEMP_THRESHOLD:
        return float(value) / 10.0
    return float(value)
