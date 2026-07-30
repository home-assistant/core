"""Support for IntelliDwell Sprinkler Controller switches."""

import logging
from typing import Any, override

from pyintellidwell import IntelliDwellConnectionError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntelliDwellConfigEntry
from .const import DOMAIN
from .coordinator import IntelliDwellCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IntelliDwellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: IntelliDwellCoordinator = config_entry.runtime_data

    entities: list[SwitchEntity] = [
        IntelliDwellZoneSwitch(coordinator, config_entry, zone_index)
        for zone_index in range(10)
    ]
    entities.extend(
        [
            IntelliDwellScheduleSwitch(coordinator, config_entry, zone_index)
            for zone_index in range(10)
        ]
    )
    async_add_entities(entities)


class IntelliDwellZoneSwitch(CoordinatorEntity[IntelliDwellCoordinator], SwitchEntity):
    """Representation of an IntelliDwell Sprinkler Zone switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliDwellCoordinator,
        config_entry: IntelliDwellConfigEntry,
        zone_index: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.zone_index = zone_index
        self._attr_translation_key = "zone"
        self._attr_translation_placeholders = {"zone_number": str(zone_index + 1)}
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_index}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="IntelliDwell Sprinkler Controller",
            manufacturer="IntelliDwell",
            model="Sprinkler Controller V2",
            configuration_url=f"http://{coordinator.client.host}",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if switch is on."""
        states = self.coordinator.data.get("relay_states", [])
        if self.zone_index < len(states):
            return states[self.zone_index] == 1
        return False

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.client.set_relay(self.zone_index, "on")
        except IntelliDwellConnectionError as err:
            raise HomeAssistantError(
                f"Error turning on zone {self.zone_index + 1}: {err}"
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.client.set_relay(self.zone_index, "off")
        except IntelliDwellConnectionError as err:
            raise HomeAssistantError(
                f"Error turning off zone {self.zone_index + 1}: {err}"
            ) from err

        await self.coordinator.async_request_refresh()


class IntelliDwellScheduleSwitch(
    CoordinatorEntity[IntelliDwellCoordinator], SwitchEntity
):
    """Representation of an IntelliDwell Zone Schedule Enable switch."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: IntelliDwellCoordinator,
        config_entry: IntelliDwellConfigEntry,
        zone_index: int,
    ) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator)
        self.zone_index = zone_index
        self._attr_translation_key = "zone_schedule"
        self._attr_translation_placeholders = {"zone_number": str(zone_index + 1)}
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_index}_schedule"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="IntelliDwell Sprinkler Controller",
            manufacturer="IntelliDwell",
            model="Sprinkler Controller V2",
            configuration_url=f"http://{coordinator.client.host}",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if schedule is enabled."""
        if not isinstance(self.coordinator.data, dict):
            return True
        schedules = self.coordinator.data.get("schedules")
        if isinstance(schedules, list) and self.zone_index < len(schedules):
            zone_info = schedules[self.zone_index]
            if isinstance(zone_info, dict):
                return bool(zone_info.get("enabled", True))
        elif isinstance(schedules, dict):
            zone_info = schedules.get(self.zone_index) or schedules.get(
                str(self.zone_index)
            )
            if isinstance(zone_info, dict):
                return bool(zone_info.get("enabled", True))
        return True

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable schedule for this zone."""
        try:
            await self.coordinator.client.set_schedule_enabled(self.zone_index, True)
        except IntelliDwellConnectionError as err:
            raise HomeAssistantError(
                f"Error enabling schedule for zone {self.zone_index + 1}: {err}"
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable schedule for this zone."""
        try:
            await self.coordinator.client.set_schedule_enabled(self.zone_index, False)
        except IntelliDwellConnectionError as err:
            raise HomeAssistantError(
                f"Error disabling schedule for zone {self.zone_index + 1}: {err}"
            ) from err

        await self.coordinator.async_request_refresh()
