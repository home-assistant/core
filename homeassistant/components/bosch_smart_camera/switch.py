"""Switch platform for the Bosch Smart Camera integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator
from .entity import BoschCameraEntity

# Serialize the cloud writes.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the privacy mode switches of the cameras."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = set(coordinator.data) - known
        known.update(new)
        async_add_entities(
            BoschPrivacyModeSwitch(coordinator, camera_id) for camera_id in new
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschPrivacyModeSwitch(BoschCameraEntity, SwitchEntity):
    """Privacy mode of a camera."""

    _attr_translation_key = "privacy_mode"

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, camera_id)
        self._attr_unique_id = f"{camera_id}_privacy_mode"

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera reports a privacy mode."""
        state = self.coordinator.account_states.get(self._camera_id)
        return (
            super().available
            and self._camera_id in self.coordinator.data
            and state is not None
            and state.privacy_mode is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the privacy mode is on."""
        state = self.coordinator.account_states.get(self._camera_id)
        return None if state is None else state.privacy_mode

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the privacy mode on."""
        await self.coordinator.async_set_privacy_mode(self._camera_id, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the privacy mode off."""
        await self.coordinator.async_set_privacy_mode(self._camera_id, False)
