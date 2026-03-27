"""Remote platform for SLZB-Ultima."""

from collections.abc import Iterable
from typing import Any

from pysmlight.exceptions import SmlightError
from pysmlight.models import IRPayload

from homeassistant.components.remote import RemoteEntity
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
        async_add_entities([SmlightRemoteEntity(coordinator)])


class SmlightRemoteEntity(SmEntity, RemoteEntity):
    """Representation of a SLZB-Ultima remote."""

    _attr_translation_key = "remote"
    _attr_is_on = True

    def __init__(self, coordinator: SmDataUpdateCoordinator) -> None:
        """Initialize the SLZB-Ultima remote."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-remote"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a sequence of commands to a device."""
        if not self.is_on:
            return

        for cmd in command:
            try:
                await self.coordinator.async_execute_command(
                    self.coordinator.client.actions.send_ir_code, IRPayload(code=cmd)
                )
            except SmlightError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="send_ir_code_failed",
                    translation_placeholders={"error": str(err)},
                ) from err
