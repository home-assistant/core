"""Vacuum platform for Eufy RoboVac."""

from collections.abc import Awaitable, Callable
from typing import Any, override

from eufy_robovac import RoboVacActivity, RoboVacConnectionError

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EufyRoboVacConfigEntry, EufyRoboVacCoordinator

ACTIVITY_MAP = {
    RoboVacActivity.CLEANING: VacuumActivity.CLEANING,
    RoboVacActivity.DOCKED: VacuumActivity.DOCKED,
    RoboVacActivity.ERROR: VacuumActivity.ERROR,
    RoboVacActivity.IDLE: VacuumActivity.IDLE,
    RoboVacActivity.PAUSED: VacuumActivity.PAUSED,
    RoboVacActivity.RETURNING: VacuumActivity.RETURNING,
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyRoboVacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an Eufy RoboVac vacuum entity."""
    async_add_entities([EufyRoboVacVacuum(entry.runtime_data)])


class EufyRoboVacVacuum(CoordinatorEntity[EufyRoboVacCoordinator], StateVacuumEntity):
    """Representation of an Eufy RoboVac."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
    )

    def __init__(self, coordinator: EufyRoboVacCoordinator) -> None:
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        info = coordinator.client.info
        self._attr_unique_id = info.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.device_id)},
            manufacturer="Eufy",
            model=info.model,
            name=info.name,
        )

    @property
    @override
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity."""
        return ACTIVITY_MAP[self.coordinator.data.activity]

    async def _async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        """Run a library command and refresh the state."""
        try:
            await command()
        except RoboVacConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_start(self, **kwargs: Any) -> None:
        """Start cleaning."""
        await self._async_command(self.coordinator.client.start)

    @override
    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._async_command(self.coordinator.client.pause)

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return the vacuum to its dock."""
        await self._async_command(self.coordinator.client.return_home)
