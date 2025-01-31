"""Component providing support for Ring buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

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

# Coordinator is used to centralize the data updates
# Actions restricted to 1 at a time
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RingButtonEntityDescription(
    ButtonEntityDescription, RingEntityDescription[RingDeviceT]
):
    """Describes a Ring button entity."""

    press_fn: Callable[[RingDeviceT], Awaitable[Any]]


BUTTON_DESCRIPTIONS: tuple[RingButtonEntityDescription[Any], ...] = (
    RingButtonEntityDescription[RingOther](
        key="open_door",
        translation_key="open_door",
        exists_fn=lambda device: device.has_capability(RingCapability.OPEN),
        press_fn=lambda device: device.async_open_door(),
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

    RingButton.process_entities(
        hass,
        devices_coordinator,
        entry=entry,
        async_add_entities=async_add_entities,
        domain=BUTTON_DOMAIN,
        descriptions=BUTTON_DESCRIPTIONS,
    )


class RingButton(RingEntity[RingDeviceT], ButtonEntity):
    """Creates a button entity."""

    entity_description: RingButtonEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingButtonEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize the button."""
        super().__init__(
            device,
            coordinator,
            description,
        )

    @exception_wrap
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self._device)
