"""Platform for Schlage select integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LockData, SchlageConfigEntry, SchlageDataUpdateCoordinator
from .entity import SchlageEntity

_DESCRIPTIONS = (
    SelectEntityDescription(
        key="auto_lock_time",
        translation_key="auto_lock_time",
        entity_category=EntityCategory.CONFIG,
        # valid values are from Schlage UI and validated by pyschlage
        options=[
            "0",
            "15",
            "30",
            "60",
            "120",
            "240",
            "300",
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SchlageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects based on a config entry."""
    coordinator = config_entry.runtime_data

    def _add_new_locks(locks: dict[str, LockData]) -> None:
        async_add_entities(
            SchlageSelect(
                coordinator=coordinator,
                description=description,
                device_id=device_id,
            )
            for device_id in locks
            for description in _DESCRIPTIONS
        )

    _add_new_locks(coordinator.data.locks)
    coordinator.new_locks_callbacks.append(_add_new_locks)


class SchlageSelect(SchlageEntity, SelectEntity):
    """Schlage select entity."""

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        description: SelectEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a SchlageSelect."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"

    @property
    def current_option(self) -> str:
        """Return the current option."""
        return str(self._lock_data.lock.auto_lock_time)

    def select_option(self, option: str) -> None:
        """Set the current option."""
        self._lock.set_auto_lock_time(int(option))
