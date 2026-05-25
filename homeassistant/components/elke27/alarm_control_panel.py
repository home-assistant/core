"""Alarm control panel platform for Elke27 areas."""

import logging
from typing import TYPE_CHECKING

from elke27_lib import AreaState, ArmMode, PanelSnapshot
from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elke27DataUpdateCoordinator
from .helpers import build_unique_id, device_info_for_entry, sanitize_name, unique_base
from .models import Elke27ConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: Elke27ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 area alarm control panels from a config entry."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    snapshot = coordinator.data
    entities = [
        Elke27AreaAlarmControlPanel(coordinator, hub, entry, area)
        for area in snapshot.areas.values()
    ]
    if entities:
        _LOGGER.debug("Adding %s area entities", len(entities))
        async_add_entities(entities)


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
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: Elke27ConfigEntry,
        area: AreaState,
    ) -> None:
        """Initialize the area entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._area_id = area.area_id
        self._attr_name = sanitize_name(area.name) or f"Area {area.area_id}"
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            area.area_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current alarm state."""
        area = _get_area(self.coordinator.data, self._area_id)
        if area is None:
            self._log_missing()
            return None
        return _area_state_to_ha(area)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_area(self.coordinator.data, self._area_id) is not None
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the area in away mode."""
        await self._async_arm(ArmMode.ARMED_AWAY, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the area in home mode."""
        await self._async_arm(ArmMode.ARMED_STAY, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm the area in night mode."""
        await self._async_arm(ArmMode.ARMED_NIGHT, code)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Arm the area with a custom bypass."""
        code = _normalize_code(code)
        for zone in self.coordinator.data.faulted_zones:
            try:
                bypassed = await self._hub.async_set_zone_bypass(
                    zone.zone_id, bypassed=True, pin=code
                )
            except Elke27PinRequiredError as err:
                msg = "PIN required to perform this action."
                raise HomeAssistantError(msg) from err
            if not bypassed:
                msg = f"Zone {zone.zone_id} bypass was not acknowledged."
                raise HomeAssistantError(msg)
        await self._async_arm(_custom_bypass_mode(), code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the area."""
        code = _normalize_code(code)
        try:
            await self._hub.async_disarm_area(self._area_id, code)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def _async_arm(self, mode: ArmMode | str, code: str | None) -> None:
        """Arm the area using the requested mode."""
        code = _normalize_code(code)
        try:
            await self._hub.async_arm_area(self._area_id, mode, code)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    def _log_missing(self) -> None:
        """Log when the area snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Area %s missing from snapshot", self._area_id)


def _get_area(snapshot: PanelSnapshot, area_id: int) -> AreaState | None:
    return snapshot.areas.get(area_id)


def _area_state_to_ha(area: AreaState) -> AlarmControlPanelState | None:
    if area.alarm_active:
        return AlarmControlPanelState.TRIGGERED
    arm_mode = area.arm_mode
    if arm_mode is None:
        return AlarmControlPanelState.DISARMED
    if arm_mode is ArmMode.DISARMED:
        return AlarmControlPanelState.DISARMED
    if arm_mode is ArmMode.ARMED_STAY:
        return AlarmControlPanelState.ARMED_HOME
    if arm_mode is ArmMode.ARMED_NIGHT:
        return AlarmControlPanelState.ARMED_NIGHT
    if arm_mode is ArmMode.ARMED_AWAY:
        return AlarmControlPanelState.ARMED_AWAY
    return None


def _custom_bypass_mode() -> str:
    return "ARMED_CUSTOM_BYPASS"


def _normalize_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = code.strip()
    if not normalized.isdigit():
        msg = "Code must be numeric."
        raise HomeAssistantError(msg)
    return normalized
