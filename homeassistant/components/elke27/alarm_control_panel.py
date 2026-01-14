"""Alarm control panel platform for Elke27 areas."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Iterable

from elke27_lib import ArmMode
from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import (
    build_unique_id,
    device_info_for_entry,
    sanitize_name,
    unique_base,
)
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 area alarm control panels from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: Elke27Hub = data[DATA_HUB]
    coordinator: Elke27DataUpdateCoordinator = data[DATA_COORDINATOR]
    known_ids: set[int] = set()

    def _async_add_areas() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Area entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27AreaAlarmControlPanel] = []
        areas = list(_iter_areas(snapshot))
        if not areas:
            _LOGGER.debug("No areas available for entity creation")
            return
        for area in areas:
            area_id = getattr(area, "area_id", None)
            if not isinstance(area_id, int):
                continue
            if area_id in known_ids:
                continue
            known_ids.add(area_id)
            entities.append(
                Elke27AreaAlarmControlPanel(
                    coordinator, hub, entry, area_id, area
                )
            )
        if entities:
            _LOGGER.debug("Adding %s area entities", len(entities))
            async_add_entities(entities)

    _async_add_areas()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_areas))


class Elke27AreaAlarmControlPanel(
    CoordinatorEntity[Elke27DataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of an Elke27 area."""

    _attr_has_entity_name = True
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        area_id: int,
        area: Any,
    ) -> None:
        """Initialize the area entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._area_id = area_id
        self._attr_name = sanitize_name(getattr(area, "name", None)) or f"Area {area_id}"
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "area",
            area_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def state(self) -> AlarmControlPanelState | None:
        """Return the current state."""
        area = _get_area(self.coordinator.data, self._area_id)
        if area is None:
            self._log_missing()
            return None
        return _area_state_to_ha(area)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        area = _get_area(self.coordinator.data, self._area_id)
        if area is None:
            return {}
        return {
            "ready": getattr(area, "ready", None),
            "trouble": getattr(area, "trouble", None),
        }

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_ready and _get_area(self.coordinator.data, self._area_id) is not None

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the area in away mode."""
        await self._async_arm(ArmMode.ARMED_AWAY, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the area in home mode."""
        await self._async_arm(ArmMode.ARMED_STAY, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm the area in night mode."""
        await self._async_arm(ArmMode.ARMED_NIGHT, code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the area."""
        code = _normalize_code(code)
        try:
            await self._hub.async_disarm_area(self._area_id, code)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    async def _async_arm(self, mode: ArmMode, code: str | None) -> None:
        """Arm the area using the requested mode."""
        code = _normalize_code(code)
        try:
            await self._hub.async_arm_area(self._area_id, mode, code)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    def _log_missing(self) -> None:
        """Log when the area snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Area %s missing from snapshot", self._area_id)


def _iter_areas(snapshot: Any) -> Iterable[Any]:
    areas = getattr(snapshot, "areas", None)
    if areas is None:
        return []
    if isinstance(areas, Mapping):
        return list(areas.values())
    if isinstance(areas, list | tuple):
        return areas
    return []


def _get_area(snapshot: Any, area_id: int) -> Any | None:
    for area in _iter_areas(snapshot):
        if getattr(area, "area_id", None) == area_id:
            return area
    return None


def _area_state_to_ha(area: Any) -> AlarmControlPanelState:
    if getattr(area, "alarm_active", False):
        return AlarmControlPanelState.TRIGGERED
    arm_mode = getattr(area, "arm_mode", None)
    if arm_mode is None:
        return AlarmControlPanelState.DISARMED
    if isinstance(arm_mode, ArmMode):
        if arm_mode is ArmMode.DISARMED:
            return AlarmControlPanelState.DISARMED
        if arm_mode is ArmMode.ARMED_STAY:
            return AlarmControlPanelState.ARMED_HOME
        if arm_mode is ArmMode.ARMED_NIGHT:
            return AlarmControlPanelState.ARMED_NIGHT
        if arm_mode is ArmMode.ARMED_AWAY:
            return AlarmControlPanelState.ARMED_AWAY
    mode_value = str(arm_mode).lower()
    if mode_value in {"disarmed", "disarm"}:
        return AlarmControlPanelState.DISARMED
    if "stay" in mode_value:
        return AlarmControlPanelState.ARMED_HOME
    if "night" in mode_value:
        return AlarmControlPanelState.ARMED_NIGHT
    if "away" in mode_value:
        return AlarmControlPanelState.ARMED_AWAY
    return AlarmControlPanelState.ARMED_AWAY
    return AlarmControlPanelState.DISARMED


def _normalize_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = code.strip()
    if not normalized.isdigit():
        raise HomeAssistantError("Code must be numeric.")
    return normalized
