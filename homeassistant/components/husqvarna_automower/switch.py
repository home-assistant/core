"""Creates a switch entity for the mower."""

import logging
from typing import TYPE_CHECKING, Any

from aioautomower.model import MowerModes, StayOutZones, Zone

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import (
    AutomowerControlEntity,
    WorkAreaControlEntity,
    _work_area_translation_key,
    handle_sending_exception,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    entities.extend(
        AutomowerScheduleSwitchEntity(mower_id, coordinator)
        for mower_id in coordinator.data
    )
    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.stay_out_zones:
            _stay_out_zones = coordinator.data[mower_id].stay_out_zones
            if _stay_out_zones is not None:
                entities.extend(
                    StayOutZoneSwitchEntity(coordinator, mower_id, stay_out_zone_uid)
                    for stay_out_zone_uid in _stay_out_zones.zones
                )
        if coordinator.data[mower_id].capabilities.work_areas:
            _work_areas = coordinator.data[mower_id].work_areas
            if _work_areas is not None:
                entities.extend(
                    WorkAreaSwitchEntity(coordinator, mower_id, work_area_id)
                    for work_area_id in _work_areas
                )
    async_add_entities(entities)

    def _async_add_new_stay_out_zones(
        mower_id: str, stay_out_zone_uids: set[str]
    ) -> None:
        async_add_entities(
            StayOutZoneSwitchEntity(coordinator, mower_id, zone_uid)
            for zone_uid in stay_out_zone_uids
        )

    def _async_add_new_work_areas(mower_id: str, work_area_ids: set[int]) -> None:
        async_add_entities(
            WorkAreaSwitchEntity(coordinator, mower_id, work_area_id)
            for work_area_id in work_area_ids
        )

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerScheduleSwitchEntity(mower_id, coordinator)
            for mower_id in mower_ids
        )
        for mower_id in mower_ids:
            mower_data = coordinator.data[mower_id]
            if (
                mower_data.capabilities.stay_out_zones
                and mower_data.stay_out_zones is not None
                and mower_data.stay_out_zones.zones is not None
            ):
                _async_add_new_stay_out_zones(
                    mower_id, set(mower_data.stay_out_zones.zones.keys())
                )
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None:
                _async_add_new_work_areas(mower_id, set(mower_data.work_areas.keys()))

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    coordinator.new_zones_callbacks.append(_async_add_new_stay_out_zones)
    coordinator.new_areas_callbacks.append(_async_add_new_work_areas)


class AutomowerScheduleSwitchEntity(AutomowerControlEntity, SwitchEntity):
    """Defining the Automower schedule switch."""

    _attr_translation_key = "enable_schedule"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{self.mower_id}_{self._attr_translation_key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.mower_attributes.mower.mode != MowerModes.HOME

    @handle_sending_exception()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.commands.park_until_further_notice(self.mower_id)

    @handle_sending_exception()
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.commands.resume_schedule(self.mower_id)


class StayOutZoneSwitchEntity(AutomowerControlEntity, SwitchEntity):
    """Defining the Automower stay out zone switch."""

    _attr_translation_key = "stay_out_zones"

    def __init__(
        self,
        coordinator: AutomowerDataUpdateCoordinator,
        mower_id: str,
        stay_out_zone_uid: str,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self.coordinator = coordinator
        self.stay_out_zone_uid = stay_out_zone_uid
        self._attr_unique_id = (
            f"{self.mower_id}_{stay_out_zone_uid}_{self._attr_translation_key}"
        )
        self._attr_translation_placeholders = {"stay_out_zone": self.stay_out_zone.name}

    @property
    def stay_out_zones(self) -> StayOutZones:
        """Return all stay out zones."""
        if TYPE_CHECKING:
            assert self.mower_attributes.stay_out_zones is not None
        return self.mower_attributes.stay_out_zones

    @property
    def stay_out_zone(self) -> Zone:
        """Return the specific stay out zone."""
        return self.stay_out_zones.zones[self.stay_out_zone_uid]

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.stay_out_zone.enabled

    @property
    def available(self) -> bool:
        """Return True if the device is available and the zones are not `dirty`."""
        return super().available and not self.stay_out_zones.dirty

    @handle_sending_exception(poll_after_sending=True)
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.commands.switch_stay_out_zone(
            self.mower_id, self.stay_out_zone_uid, switch=False
        )

    @handle_sending_exception(poll_after_sending=True)
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.commands.switch_stay_out_zone(
            self.mower_id, self.stay_out_zone_uid, switch=True
        )


class WorkAreaSwitchEntity(WorkAreaControlEntity, SwitchEntity):
    """Defining the Automower work area switch."""

    def __init__(
        self,
        coordinator: AutomowerDataUpdateCoordinator,
        mower_id: str,
        work_area_id: int,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator, work_area_id)
        key = "work_area"
        self._attr_translation_key = _work_area_translation_key(work_area_id, key)
        self._attr_unique_id = f"{mower_id}_{work_area_id}_{key}"
        if self.work_area_attributes.name == "my_lawn":
            self._attr_translation_placeholders = {
                "work_area": self.work_area_attributes.name
            }
        else:
            self._attr_name = self.work_area_attributes.name

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.work_area_attributes.enabled

    @handle_sending_exception(poll_after_sending=True)
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.commands.workarea_settings(
            self.mower_id, self.work_area_id, enabled=False
        )

    @handle_sending_exception(poll_after_sending=True)
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.commands.workarea_settings(
            self.mower_id, self.work_area_id, enabled=True
        )
