"""RVC entity for Electrolux Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, override

from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)
VACUUM_ACTIVITY_MAP = {
    1: VacuumActivity.CLEANING,  # Cleaning
    2: VacuumActivity.PAUSED,  # PausedCleaning
    3: VacuumActivity.CLEANING,  # SpotCleaning
    4: VacuumActivity.PAUSED,  # PausedSpotCleaning
    5: VacuumActivity.RETURNING,  # Return
    6: VacuumActivity.PAUSED,  # PausedReturn
    7: VacuumActivity.RETURNING,  # ReturnForPitstop
    8: VacuumActivity.PAUSED,  # PausedReturnForPitstop
    9: VacuumActivity.DOCKED,  # Charging
    10: VacuumActivity.IDLE,  # Sleeping
    11: VacuumActivity.ERROR,  # Error
    12: VacuumActivity.DOCKED,  # Pitstop
    13: VacuumActivity.IDLE,  # ManualSteering
    14: VacuumActivity.IDLE,  # FWUpgrade
    "inProgress": VacuumActivity.CLEANING,
    "goingHome": VacuumActivity.RETURNING,
    "idle": VacuumActivity.IDLE,
    "paused": VacuumActivity.PAUSED,
    "sleeping": VacuumActivity.DOCKED,
}

ELECTROLUX_TO_HA_FAN_MODES: dict[str | int, str] = {
    1: "silent",
    2: "smart",
    3: "power",
    "energySaving": "energy_saving",
    "powerful": "powerful",
    "quiet": "quiet",
    "standard": "standard",
    "maxPower": "max_power",
    "max": "max",
}

HA_TO_ELECTROLUX_MODES = {v: k for k, v in ELECTROLUX_TO_HA_FAN_MODES.items()}

CLEAN_ZONES_COMMAND = "clean_zones"


@dataclass(frozen=True, kw_only=True)
class ElectroluxVacuumDescription[T: RVCAppliance](StateVacuumEntityDescription):
    """Custom sensor description for Electrolux vacuums."""

    exists_fn: Callable[[T], bool] = lambda *args: True
    get_segments_fn: (
        Callable[[ApplianceClient, str], Awaitable[list[Segment]]] | None
    ) = None
    clean_segments_command_fn: Callable[[T, str, list[str]], dict[str, Any]] | None = (
        None
    )


def _is_700series_vacuum(appliance_data: RVCAppliance) -> bool:
    """Check if the appliance is a 700series vacuum."""
    return appliance_data.appliance.applianceType == "700series"


def _is_purei9_vacuum(appliance_data: RVCAppliance) -> bool:
    """Check if the appliance is a PUREi9 vacuum."""
    return appliance_data.appliance.applianceType == "PUREi9"


def _is_gordias_vacuum(appliance_data: RVCAppliance) -> bool:
    """Check if the appliance is a Gordias vacuum."""
    return appliance_data.appliance.applianceType == "Gordias"


def _is_cybele_vacuum(appliance_data: RVCAppliance) -> bool:
    """Check if the appliance is a Cybele vacuum."""
    return appliance_data.appliance.applianceType == "Cybele"


async def _get_interactive_maps_segments(
    client: ApplianceClient, appliance_id: str
) -> list[Segment]:
    segments: list[Segment] = []
    interactive_maps = await client.get_interactive_maps(appliance_id)
    for interactive_map in interactive_maps:
        map_id = interactive_map.get("id")
        map_name = interactive_map.get("name")
        zones = interactive_map.get("zones") or []
        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name")
            zone_type = zone.get("zoneType")
            if zone_type == "clean":
                segments.append(
                    Segment(id=f"{map_id}_{zone_id}", name=f"{map_name}: {zone_name}")
                )

    return segments


async def _get_memory_maps_segments(
    client: ApplianceClient, appliance_id: str
) -> list[Segment]:
    segments: list[Segment] = []
    memory_maps = await client.get_memory_maps(appliance_id)
    for memory_map in memory_maps:
        map_id = memory_map.get("id")
        map_name = memory_map.get("name")
        rooms = memory_map.get("rooms") or []
        for room in rooms:
            room_id = room.get("Id")
            room_name = room.get("Name")
            segments.append(
                Segment(id=f"{map_id}_{room_id}", name=f"{map_name}: {room_name}")
            )

    return segments


def _get_clean_segments_command_purei9(
    appliance_data: RVCAppliance, map_id: str, zone_ids: list[str]
) -> dict[str, Any]:
    return appliance_data.get_start_zone_cleaning_command(map_id, zone_ids)


def _get_clean_segments_command_gordias(
    appliance_data: RVCAppliance, map_id: str, zone_ids: list[str]
) -> dict[str, Any]:
    int_map_id = int(map_id)
    room_ids = [int(zone_id) for zone_id in zone_ids]
    return appliance_data.get_gordias_start_room_cleaning_command(int_map_id, room_ids)


def _get_clean_segments_command_cybele(
    appliance_data: RVCAppliance, map_id: str, zone_ids: list[str]
) -> dict[str, Any]:
    int_map_id = int(map_id)
    room_ids_names = [(int(zone_id), "") for zone_id in zone_ids]
    return appliance_data.get_cybele_start_room_cleaning_command(
        int_map_id,
        room_ids_names,
        global_settings_cleaning=True,
    )


VACUUM_DESCRIPTIONS: tuple[ElectroluxVacuumDescription, ...] = (
    ElectroluxVacuumDescription(
        key="700series", translation_key="rvc", exists_fn=_is_700series_vacuum
    ),
    ElectroluxVacuumDescription(
        key="purei9",
        translation_key="rvc",
        exists_fn=_is_purei9_vacuum,
        get_segments_fn=_get_interactive_maps_segments,
        clean_segments_command_fn=_get_clean_segments_command_purei9,
    ),
    ElectroluxVacuumDescription(
        key="gordias",
        translation_key="rvc",
        exists_fn=_is_gordias_vacuum,
        get_segments_fn=_get_memory_maps_segments,
        clean_segments_command_fn=_get_clean_segments_command_gordias,
    ),
    ElectroluxVacuumDescription(
        key="cybele",
        translation_key="rvc",
        exists_fn=_is_cybele_vacuum,
        get_segments_fn=_get_memory_maps_segments,
        clean_segments_command_fn=_get_clean_segments_command_cybele,
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, RVCAppliance):
        entities.extend(
            RvcEntity(appliance_data, coordinator, description)
            for description in VACUUM_DESCRIPTIONS
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set RVC entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class RvcEntity(ElectroluxBaseEntity[RVCAppliance], StateVacuumEntity):
    """Representation of an Electrolux RVC."""

    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.FAN_SPEED
    )
    _entity_description: ElectroluxVacuumDescription[RVCAppliance]

    def __init__(
        self,
        appliance_data: RVCAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxVacuumDescription[RVCAppliance],
    ) -> None:
        """Initialize the climate device."""
        super().__init__(appliance_data, coordinator, "rvc")
        self._entity_description = description
        self._attr_name = None
        self._model = self._appliance_data.appliance.applianceType

        if (
            description.clean_segments_command_fn is not None
            and description.get_segments_fn is not None
        ):
            self._attr_supported_features |= VacuumEntityFeature.CLEAN_AREA
        self._attr_fan_speed_list = self._get_available_modes()
        self._attr_fan_speed = None
        self._attr_activity = VacuumActivity.IDLE

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            self._entity_description.clean_segments_command_fn is not None
            and self._entity_description.get_segments_fn is not None
        ):
            self.coordinator.add_livestream_opening_callback(
                self._check_for_segments_update
            )

    @override
    async def async_will_remove_from_hass(self) -> None:
        if (
            self._entity_description.clean_segments_command_fn is not None
            and self._entity_description.get_segments_fn is not None
        ):
            self.coordinator.remove_livestream_opening_callback(
                self._check_for_segments_update
            )
        await super().async_will_remove_from_hass()

    async def send_device_command(self, command: dict[str, Any]) -> None:
        """Send a command to the appliance and refresh."""
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    def _update_attr_state(self) -> bool:
        state_updated = False

        new_activity = self._get_current_activity()
        if new_activity != self._attr_activity:
            self._attr_activity = new_activity
            state_updated = True

        new_fan_speed = self._get_current_mode()
        if new_fan_speed != self._attr_fan_speed:
            self._attr_fan_speed = new_fan_speed
            state_updated = True

        return state_updated

    def _get_current_activity(self) -> VacuumActivity:
        if self._appliance_data.is_docked():
            return VacuumActivity.DOCKED

        reported_value = self._appliance_data.get_current_state()

        return VACUUM_ACTIVITY_MAP.get(reported_value, VacuumActivity.IDLE)

    def _get_current_mode(self) -> str | None:
        raw_mode = self._appliance_data.get_current_mode()
        mode = ELECTROLUX_TO_HA_FAN_MODES.get(raw_mode)
        if mode is None:
            _LOGGER.warning("Unmapped RVC mode found: %s", raw_mode)
            return None
        return mode

    def _get_available_modes(self) -> list[str]:
        modes = self._appliance_data.get_supported_modes()
        mapped_modes = []

        for mode in modes:
            readable = ELECTROLUX_TO_HA_FAN_MODES.get(mode)
            if readable is None:
                _LOGGER.warning("Unmapped RVC mode found: %s", mode)
            else:
                mapped_modes.append(readable)

        return list(dict.fromkeys(mapped_modes))

    @override
    async def async_start(self, **kwargs: Any) -> None:
        """Start or resume the cleaning task."""
        if self._appliance_data.is_paused():
            command = self._appliance_data.get_resume_command()
        else:
            command = self._appliance_data.get_start_command()
        await self.send_device_command(command)

    @override
    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner, do not return to base."""
        command = self._appliance_data.get_stop_command()
        await self.send_device_command(command)

    @override
    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the cleaning task."""
        command = self._appliance_data.get_pause_command()
        await self.send_device_command(command)

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        command = self._appliance_data.get_dock_command()
        await self.send_device_command(command)

    @override
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed."""
        command = self._appliance_data.get_set_mode_command(
            HA_TO_ELECTROLUX_MODES[fan_speed]
        )
        await self.send_device_command(command)

    @override
    async def async_get_segments(self) -> list[Segment]:
        """Get the segments for the vacuum cleaner."""
        description = self._entity_description
        # CLEAN_AREA feature is only supported if vacuum has get_segments_fn and clean_segments_command_fn
        if TYPE_CHECKING:
            assert description.get_segments_fn is not None
        return await description.get_segments_fn(
            self.coordinator.client, self._appliance_id
        )

    @override
    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments."""

        map_id_set = {segment_id.split("_")[0] for segment_id in segment_ids}
        if len(map_id_set) > 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="multiple_map_ids",
            )
        map_id = map_id_set.pop()
        zone_ids = [segment_id[len(map_id) + 1 :] for segment_id in segment_ids]

        description = self._entity_description
        # CLEAN_AREA feature is only supported if vacuum has get_segments_fn and clean_segments_command_fn
        if TYPE_CHECKING:
            assert description.clean_segments_command_fn is not None
        command = description.clean_segments_command_fn(
            self._appliance_data, map_id, zone_ids
        )

        await self.send_device_command(command)

    async def _check_for_segments_update(self) -> None:
        """Check for updates to the segments for the vacuum cleaner."""
        description = self._entity_description
        # CLEAN_AREA feature is only supported if vacuum has get_segments_fn and clean_segments_command_fn
        if TYPE_CHECKING:
            assert description.get_segments_fn is not None
        segments = await description.get_segments_fn(
            self.coordinator.client, self._appliance_id
        )

        last_seen_segments = self.last_seen_segments or []

        if set(segments) != set(last_seen_segments):
            self.async_create_segments_issue()
