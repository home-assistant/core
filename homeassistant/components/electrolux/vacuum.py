"""RVC entity for Electrolux Integration."""

import logging
from typing import Any, override

from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, RVCAppliance):
        entities.append(
            RvcEntity(appliance_data=appliance_data, coordinator=coordinator)
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

    def __init__(
        self,
        appliance_data: RVCAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(appliance_data, coordinator, "rvc")
        self._attr_name = None
        self._model = self._appliance_data.appliance.applianceType

        if self._model in ["PUREi9", "Gordias", "Cybele"]:
            self._attr_supported_features |= (
                VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.CLEAN_AREA
            )
        self._attr_fan_speed_list = self._get_available_modes()
        self._attr_fan_speed = None
        self._attr_activity = VacuumActivity.IDLE

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
        if self._model == "PUREi9":
            return await _get_interactive_maps_segments(
                self.coordinator.client, self._appliance_id
            )
        if self._model in ["Gordias", "Cybele"]:
            return await _get_memory_maps_segments(
                self.coordinator.client, self._appliance_id
            )
        return []

    @override
    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments."""
        if not segment_ids:
            raise ServiceValidationError("No segments specified for cleaning")

        map_id_set = {segment_id.split("_")[0] for segment_id in segment_ids}
        if len(map_id_set) > 1:
            raise ServiceValidationError(
                "Can't perform cleaning command: segments from multiple maps selected"
            )
        map_id = map_id_set.pop()

        zone_ids = [segment_id[len(map_id) + 1 :] for segment_id in segment_ids]
        if self._model == "PUREi9":
            command = self._appliance_data.get_start_zone_cleaning_command(
                map_id, zone_ids
            )
        elif self._model == "Gordias":
            int_map_id = int(map_id)
            room_ids = [int(zone_id) for zone_id in zone_ids]
            command = self._appliance_data.get_gordias_start_room_cleaning_command(
                int_map_id, room_ids
            )
        elif self._model == "Cybele":
            int_map_id = int(map_id)
            room_ids_names = [(int(zone_id), "") for zone_id in zone_ids]
            command = self._appliance_data.get_cybele_start_room_cleaning_command(
                int_map_id,
                room_ids_names,
                global_settings_cleaning=True,
            )
        else:
            raise ServiceValidationError(
                "The robot vacuum does not support segment cleaning"
            )

        await self.send_device_command(command)

    @override
    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle custom vacuum commands."""

        _LOGGER.debug("Received send_command: %s, params: %s", command, params)

        if not isinstance(params, dict):
            raise ServiceValidationError("Incorrect parameters provided")

        device_command: dict[str, Any] | None = None

        if command == "clean_zones":
            map_id = params.get("map_id")
            zone_ids = params.get("zone_ids", []) if params else []
            power_mode = params.get("power_mode", 2)
            if map_id:
                device_command = self._appliance_data.get_start_zone_cleaning_command(
                    map_id, zone_ids, power_mode
                )
            else:
                _LOGGER.warning("Map id is missing")
        elif command == "clean_gordias_rooms":
            map_id = params.get("map_id")
            room_ids = params.get("room_ids", []) if params else []
            sweep_mode = params.get("sweepMode", 0)
            vacuum_mode = params.get("vacuumMode", "standard")
            water_pump_rate = params.get("waterPumpRate", "off")
            repetitions = params.get("numberOfCleaningRepetitions", 1)
            if map_id:
                device_command = (
                    self._appliance_data.get_gordias_start_room_cleaning_command(
                        map_id,
                        room_ids,
                        sweep_mode,
                        vacuum_mode,
                        water_pump_rate,
                        repetitions,
                    )
                )
            else:
                _LOGGER.warning("Map id is missing")

        elif command == "clean_cybele_rooms":
            map_id = params.get("map_id")
            room_ids_names = params.get("room_ids_names", []) if params else []
            global_settings_cleaning = params.get("globalSettingsCleaning", True)
            cleaning_type = params.get("cleaningType", "vacuum")
            vacuum_mode = params.get("vacuumMode", "standard")
            water_pump_rate = params.get("waterPumpRate", "off")
            repetitions = params.get("numberOfCleaningRepetitions", 1)
            if map_id:
                device_command = (
                    self._appliance_data.get_cybele_start_room_cleaning_command(
                        map_id,
                        room_ids_names,
                        global_settings_cleaning,
                        cleaning_type,
                        vacuum_mode,
                        water_pump_rate,
                        repetitions,
                    )
                )
            else:
                _LOGGER.warning("Map id is missing")
        else:
            _LOGGER.warning("Unknown command: %s", command)

        if device_command:
            await self.send_device_command(device_command)


async def _get_interactive_maps_segments(
    client: ApplianceClient, appliance_id: str
) -> list[Segment]:
    segments: list[Segment] = []
    interactive_maps = await client.get_interactive_maps(appliance_id)
    for interactive_map in interactive_maps:
        map_id = interactive_map.get("id")
        map_name = interactive_map.get("name")
        zones = interactive_map.get("zones", [])
        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name")
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
        rooms = memory_map.get("rooms", [])
        for room in rooms:
            room_id = room.get("id")
            room_name = room.get("name")
            segments.append(
                Segment(id=f"{map_id}_{room_id}", name=f"{map_name}: {room_name}")
            )

    return segments
