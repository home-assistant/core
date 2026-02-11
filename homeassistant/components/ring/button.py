"""Component providing support for Ring buttons."""

from __future__ import annotations

from ring_doorbell import RingOther

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingEntity, exception_wrap

# Coordinator is used to centralize the data updates
# Actions restricted to 1 at a time
PARALLEL_UPDATES = 1

BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="open_door", translation_key="open_door"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the buttons for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingDoorButton(device, devices_coordinator, BUTTON_DESCRIPTION)
        for device in ring_data.devices.other
        if device.has_capability("open")
    )


class RingDoorButton(RingEntity[RingOther], ButtonEntity):
    """Creates a button to open the ring intercom door."""

    def __init__(
        self,
        device: RingOther,
        coordinator: RingDataCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            device,
            coordinator,
        )
        self.entity_description = description
        self._attr_unique_id = f"{device.id}-{description.key}"

    @exception_wrap
    async def async_press(self) -> None:
        """Open the door."""
        await self._device.async_open_door()
