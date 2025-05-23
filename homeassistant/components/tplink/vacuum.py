"""Support for TPLink vacuum."""

from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from typing import Any, Final

from kasa import Device, Module
from kasa.smart.modules.clean import Clean, Status
import voluptuous as vol

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import entity_platform
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkModuleEntity,
    TPLinkModuleEntityDescription,
    async_refresh_after,
)
from .map_parser import GetRoomsResponse, MapData, TpLinkMapParser

# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0

# Upstream state to VacuumActivity
STATUS_TO_ACTIVITY = {
    Status.Idle: VacuumActivity.IDLE,
    Status.Cleaning: VacuumActivity.CLEANING,
    Status.GoingHome: VacuumActivity.RETURNING,
    Status.Charging: VacuumActivity.DOCKED,
    Status.Charged: VacuumActivity.DOCKED,
    Status.Undocked: VacuumActivity.IDLE,
    Status.Paused: VacuumActivity.PAUSED,
    Status.Error: VacuumActivity.ERROR,
}

GET_ROOM_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {vol.Optional("map_id"): int}
)

CLEAN_ROOMS_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {
        vol.Required("map_id"): int,
        vol.Required("room_ids"): [int],
    }
)

CUSTOM_QUERY_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {
        vol.Required("query"): str,
        vol.Optional("params"): dict,
    }
)


@dataclass(frozen=True, kw_only=True)
class TPLinkVacuumEntityDescription(
    StateVacuumEntityDescription, TPLinkModuleEntityDescription
):
    """Base class for vacuum entity description."""


VACUUM_DESCRIPTIONS: tuple[TPLinkVacuumEntityDescription, ...] = (
    TPLinkVacuumEntityDescription(
        key="vacuum",
        translation_key="vacuum",
        exists_fn=lambda dev, _: Module.Clean in dev.modules,
        entity_name_fn=lambda _, __: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up vacuum entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkModuleEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            entity_class=TPLinkVacuumEntity,
            descriptions=VACUUM_DESCRIPTIONS,
            platform_domain=VACUUM_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "get_maps",
        None,
        TPLinkVacuumEntity.get_maps.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        "get_rooms",
        GET_ROOM_SERVICE_SCHEMA,
        TPLinkVacuumEntity.get_rooms.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        "get_current_room",
        None,
        TPLinkVacuumEntity.get_current_room.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        "clean_rooms",
        CLEAN_ROOMS_SERVICE_SCHEMA,
        TPLinkVacuumEntity.clean_rooms.__name__,
        supports_response=SupportsResponse.NONE,
    )

    platform.async_register_entity_service(
        "custom_query",
        CUSTOM_QUERY_SERVICE_SCHEMA,
        TPLinkVacuumEntity.custom_query.__name__,
        supports_response=SupportsResponse.ONLY,
    )


class TPLinkVacuumEntity(CoordinatedTPLinkModuleEntity, StateVacuumEntity):
    """Representation of a tplink vacuum."""

    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
    )

    entity_description: TPLinkVacuumEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        description: TPLinkVacuumEntityDescription,
        *,
        parent: Device,
    ) -> None:
        """Initialize the vacuum entity."""
        super().__init__(device, coordinator, description, parent=parent)
        self._vacuum_module: Clean = device.modules[Module.Clean]
        if speaker := device.modules.get(Module.Speaker):
            self._speaker_module = speaker
            self._attr_supported_features |= VacuumEntityFeature.LOCATE

        if (
            fanspeed_feat := self._vacuum_module.get_feature("fan_speed_preset")
        ) and fanspeed_feat.choices:
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED
            self._attr_fan_speed_list = [c.lower() for c in fanspeed_feat.choices]

    @async_refresh_after
    async def async_start(self) -> None:
        """Start cleaning."""
        await self._vacuum_module.start()

    @async_refresh_after
    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._vacuum_module.pause()

    @async_refresh_after
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return home."""
        await self._vacuum_module.return_home()

    @async_refresh_after
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self._vacuum_module.set_fan_speed_preset(fan_speed.capitalize())

    async def custom_query(
        self, query: str, params: dict | None = None
    ) -> ServiceResponse:
        """Execute a custom query."""
        return await self._vacuum_module.call(query, params)

    async def clean_rooms(self, map_id: int, room_ids: list[int]) -> None:
        """Start cleaning the specified rooms."""
        if self._vacuum_module.status is Status.Paused:
            await self._vacuum_module.resume()
            return

        await self._vacuum_module.call(
            "setSwitchClean",
            {
                "clean_mode": 3,
                "clean_on": True,
                "clean_order": True,
                "force_clean": False,
                "map_id": map_id,
                "room_list": room_ids,
            },
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        await self._speaker_module.locate()

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        return self._vacuum_module.battery

    async def get_maps(self) -> ServiceResponse:
        """Get map information such as map id and room ids."""
        res = await self._vacuum_module.call("getMapInfo")

        return {
            "maps": [
                {
                    "id": vacuum_map["map_id"],
                    "name": b64decode(vacuum_map["map_name"]).decode("utf-8"),
                    # JsonValueType does not accept a int as a key - was not a
                    # issue with previous asdict() implementation.
                    "rooms": (await self._get_rooms(vacuum_map["map_id"]))["rooms"],  # type: ignore[dict-item]
                }
                for vacuum_map in res["getMapInfo"]["map_list"]
            ]
        }

    async def get_rooms(self, map_id: int | None) -> ServiceResponse:
        """Get room information for a specific map."""
        if map_id is None:
            map_id = -1

        return await self._get_rooms(map_id)  # type: ignore[return-value]

    async def _get_rooms(self, map_id: int) -> GetRoomsResponse:
        res = await self._vacuum_module.call("getMapData", {"map_id": map_id})
        map_data: MapData = res["getMapData"]
        parser = TpLinkMapParser(map_data)
        return {"rooms": parser.get_rooms(), "map_id": map_data["map_id"]}

    async def get_current_room(self) -> ServiceResponse:
        """Get the current position of the vacuum from the map."""
        # Get the current map
        res = await self._vacuum_module.call("getMapData", {"map_id": -1})
        parser = TpLinkMapParser(res["getMapData"])
        return parser.get_current_room()  # type: ignore[return-value]

    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_activity = STATUS_TO_ACTIVITY.get(self._vacuum_module.status)
        if self._vacuum_module.has_feature("fan_speed_preset"):
            self._attr_fan_speed = self._vacuum_module.fan_speed_preset.lower()
        return True
