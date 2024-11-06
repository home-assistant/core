"""Component providing support for Ring buttons."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ring_doorbell import RingCapability, RingOther

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingDeviceT, RingEntity, RingEntityDescription, exception_wrap


@dataclass(frozen=True, kw_only=True)
class RingButtonEntityDescription(
    ButtonEntityDescription, RingEntityDescription[RingDeviceT]
):
    """Describes a Ring button entity."""


BUTTONS: Sequence[RingButtonEntityDescription] = (
    RingButtonEntityDescription(
        key="open_door",
        translation_key="open_door",
        exists_fn=lambda device: device.has_capability(RingCapability.OPEN),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the buttons for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    RingDoorButton.process_entities(
        hass,
        devices_coordinator,
        entry=entry,
        async_add_entities=async_add_entities,
        domain=BUTTON_DOMAIN,
        descriptions=BUTTONS,
    )


class RingDoorButton(RingEntity[RingOther], ButtonEntity):
    """Creates a button to open the ring intercom door."""

    def __init__(
        self,
        device: RingOther,
        coordinator: RingDataCoordinator,
        description: RingEntityDescription[RingOther],
    ) -> None:
        """Initialize the button."""
        super().__init__(
            device,
            coordinator,
            description,
        )

    @exception_wrap
    async def async_press(self) -> None:
        """Open the door."""
        await self._device.async_open_door()
