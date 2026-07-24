"""Vacuum entities for the Beatbot integration."""

from typing import Any, override

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity
from .iot.category import (
    CATEGORY_MAP,
    VACUUM_FEATURES_BY_CATEGORY,
    ProductCategory,
    vacuum_activity,
    vacuum_features_from_capabilities,
)
from .iot.const import INTERFACE_PAUSE, INTERFACE_RETURN_TO_BASE, INTERFACE_START

VACUUM_TRANSLATION_KEYS = {
    ProductCategory.POOL_CLEAN_BOT: "beatbot_pool_vacuum",
    ProductCategory.CLEAN_BASE_STATION: "beatbot_clean_base_station_vacuum",
}


class BeatbotVacuum(BeatbotEntity, StateVacuumEntity):
    """Represent a Beatbot cleaner as a vacuum entity."""

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Beatbot vacuum."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        category = CATEGORY_MAP.get(
            self.coordinator.data[self._device_id].product_category
        )
        assert category is not None
        if translation_key := VACUUM_TRANSLATION_KEYS.get(category):
            self._attr_translation_key = translation_key
        # Actions are exposed only when explicitly advertised by the device.
        # Devices without vacuum action capabilities remain STATE-only.
        features = vacuum_features_from_capabilities(self.data.capabilities)
        if features is None:
            features = VACUUM_FEATURES_BY_CATEGORY.get(category, VacuumEntityFeature(0))
        self._attr_supported_features = features
        self._category = category

    @property
    @override
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity."""
        return vacuum_activity(
            self._category, self.data.work_status, self.data.error_code
        )

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
