"""Remote platform for SLZB-Ultima."""

import asyncio
from collections.abc import Iterable
from typing import Any

from pysmlight.exceptions import SmlightError
from pysmlight.models import IRPayload

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize remote for SLZB-Ultima device."""
    coordinator = entry.runtime_data.data

    if coordinator.data.info.has_peripherals:
        async_add_entities([SmRemoteEntity(coordinator)])


class SmRemoteEntity(SmEntity, RemoteEntity):
    """Representation of a SLZB-Ultima remote."""

    _attr_translation_key = "remote"
    _attr_is_on = True

    def __init__(self, coordinator: SmDataUpdateCoordinator) -> None:
        """Initialize the SLZB-Ultima remote."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-remote"

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a sequence of commands to a device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for cmd in command:
                try:
                    await self.coordinator.async_execute_command(
                        self.coordinator.client.actions.send_ir_code,
                        IRPayload(code=cmd),
                    )
                except SmlightError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="send_ir_code_failed",
                        translation_placeholders={"error": str(err)},
                    ) from err

                await asyncio.sleep(delay_secs)
