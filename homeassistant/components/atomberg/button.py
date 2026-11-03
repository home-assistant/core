"""Button platform for Atomberg smart locks."""

from typing import override

from atomberg_api import DEVICE_TYPE_LOCK, AtombergDevice

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergGuestPinButton(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_LOCK)
    )


class AtombergGuestPinButton(AtombergEntity, ButtonEntity):
    """Generate a temporary guest PIN and show it in a notification."""

    _attr_translation_key = "guest_pin"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device, "guest_pin")

    @override
    async def async_press(self) -> None:
        """Generate the PIN."""
        pin = await self.coordinator.async_generate_guest_pin(self.device)
        persistent_notification.async_create(
            self.hass,
            (
                f"PIN: {pin.get('otp')}\n"
                f"Valid from: {pin.get('validStartTime', 'not limited')}\n"
                f"Valid until: {pin.get('validEndTime', 'not limited')}"
            ),
            title=f"{self.device.name} guest PIN",
            notification_id=f"{DOMAIN}_{self.device.device_id}_guest_pin",
        )
