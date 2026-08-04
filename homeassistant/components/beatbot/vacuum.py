"""Vacuum entities for the Beatbot integration."""

from typing import Any, override

from beatbot_cloud import (
    BeatbotCapability,
    DeviceStatus,
    ProductCategory,
    error_mask_for,
    status_for,
)

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .const import (
    INTERFACE_PAUSE,
    INTERFACE_RETURN_TO_BASE,
    INTERFACE_START,
    INTERFACE_VACUUM_STATE,
)
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity

VACUUM_ACTIVITY_BY_STATUS = {
    DeviceStatus.STANDBY: VacuumActivity.IDLE,
    DeviceStatus.GOTO_CHARGE: VacuumActivity.RETURNING,
    DeviceStatus.CHARGING: VacuumActivity.DOCKED,
    DeviceStatus.CHARGE_DONE: VacuumActivity.DOCKED,
    DeviceStatus.PAUSED: VacuumActivity.PAUSED,
    DeviceStatus.CLEANING: VacuumActivity.CLEANING,
    DeviceStatus.SLEEP: VacuumActivity.IDLE,
    DeviceStatus.RETURN_TRIP: VacuumActivity.RETURNING,
    DeviceStatus.CLEAN_DONE: VacuumActivity.IDLE,
    DeviceStatus.REMOTE_CONTROL: VacuumActivity.CLEANING,
    DeviceStatus.CLEAN_WAIT: VacuumActivity.IDLE,
    DeviceStatus.WIFI_CONNECT: VacuumActivity.IDLE,
    DeviceStatus.DIVING: VacuumActivity.CLEANING,
    DeviceStatus.EMERGE: VacuumActivity.CLEANING,
    DeviceStatus.AUTO_DOCK: VacuumActivity.RETURNING,
    DeviceStatus.FINISH_CONNECT: VacuumActivity.RETURNING,
    DeviceStatus.DOCK: VacuumActivity.DOCKED,
    DeviceStatus.SELF_CLEANING: VacuumActivity.CLEANING,
    DeviceStatus.REPLENISH_ENERGY: VacuumActivity.IDLE,
    DeviceStatus.CHASE_LIGHT: VacuumActivity.CLEANING,
    DeviceStatus.DOCK_DONE: VacuumActivity.DOCKED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot vacuum entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        BeatbotVacuum(coordinator, device_id) for device_id in coordinator.data
    )


def vacuum_activity(work_status: int, error_code: int) -> VacuumActivity:
    """Return the vacuum activity for a Beatbot pool cleaner."""
    category = ProductCategory.POOL_CLEAN_BOT
    if error_code & error_mask_for(category):
        return VacuumActivity.ERROR
    if status := status_for(category, work_status):
        return VACUUM_ACTIVITY_BY_STATUS[status]
    return VacuumActivity.IDLE


def vacuum_features_from_capabilities(
    capabilities: dict[str, BeatbotCapability],
) -> VacuumEntityFeature | None:
    """Derive vacuum features from advertised capabilities."""
    if not capabilities:
        return None

    if not {
        INTERFACE_VACUUM_STATE,
        INTERFACE_START,
        INTERFACE_PAUSE,
        INTERFACE_RETURN_TO_BASE,
    }.intersection(capabilities):
        return None

    features = VacuumEntityFeature(0)
    if (
        state := capabilities.get(INTERFACE_VACUUM_STATE)
    ) is not None and state.retrievable:
        features |= VacuumEntityFeature.STATE
    if (
        start := capabilities.get(INTERFACE_START)
    ) is not None and not start.non_controllable:
        features |= VacuumEntityFeature.START
    if (
        pause := capabilities.get(INTERFACE_PAUSE)
    ) is not None and not pause.non_controllable:
        features |= VacuumEntityFeature.PAUSE
    if (
        return_to_base := capabilities.get(INTERFACE_RETURN_TO_BASE)
    ) is not None and not return_to_base.non_controllable:
        features |= VacuumEntityFeature.RETURN_HOME
    return features


class BeatbotVacuum(BeatbotEntity, StateVacuumEntity):
    """Represent a Beatbot pool cleaner."""

    _attr_translation_key = "beatbot_pool_vacuum"

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize the Beatbot vacuum."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        features = vacuum_features_from_capabilities(self.data.capabilities)
        self._attr_supported_features = VacuumEntityFeature.STATE | (
            features or VacuumEntityFeature(0)
        )

    @property
    @override
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity."""
        return vacuum_activity(self.data.work_status, self.data.error_code)

    @property
    @override
    def available(self) -> bool:
        """Return whether the vacuum can be controlled."""
        return self.data.is_online and self.coordinator.last_update_success

    @override
    async def async_start(self) -> None:
        """Start cleaning."""
        await self._async_send_command(
            lambda: self.coordinator.api.send_action(self._device_id, INTERFACE_START)
        )
        self.coordinator.async_schedule_device_state_refresh(self._device_id)

    @override
    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._async_send_command(
            lambda: self.coordinator.api.send_action(self._device_id, INTERFACE_PAUSE)
        )
        self.coordinator.async_schedule_device_state_refresh(self._device_id)

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return the cleaner to its base."""
        await self._async_send_command(
            lambda: self.coordinator.api.send_action(
                self._device_id, INTERFACE_RETURN_TO_BASE
            )
        )
        self.coordinator.async_schedule_device_state_refresh(self._device_id)
