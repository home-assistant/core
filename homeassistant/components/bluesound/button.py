"""Button entities for Bluesound."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyblu import Player, SyncStatus

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BluesoundCoordinator
from .media_player import DEFAULT_PORT
from .utils import format_unique_id

if TYPE_CHECKING:
    from . import BluesoundConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluesoundConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bluesound entry."""

    async_add_entities(
        [
            SetSleepTimerButton(
                config_entry.runtime_data.coordinator,
                config_entry.runtime_data.player,
                config_entry.data[CONF_PORT],
            ),
            ClearSleepTimerButton(
                config_entry.runtime_data.coordinator,
                config_entry.runtime_data.player,
                config_entry.data[CONF_PORT],
            ),
        ],
        update_before_add=True,
    )


def generate_device_info(sync_status: SyncStatus, port: int) -> DeviceInfo:
    """Generate device info."""
    if port == DEFAULT_PORT:
        return DeviceInfo(
            identifiers={(DOMAIN, format_mac(sync_status.mac))},
            connections={(CONNECTION_NETWORK_MAC, format_mac(sync_status.mac))},
            name=sync_status.name,
            manufacturer=sync_status.brand,
            model=sync_status.model_name,
            model_id=sync_status.model,
        )

    return DeviceInfo(
        identifiers={(DOMAIN, format_unique_id(sync_status.mac, port))},
        name=sync_status.name,
        manufacturer=sync_status.brand,
        model=sync_status.model_name,
        model_id=sync_status.model,
        via_device=(DOMAIN, format_mac(sync_status.mac)),
    )


class SetSleepTimerButton(CoordinatorEntity[BluesoundCoordinator], ButtonEntity):
    """Representation of a sleep timer button."""

    def __init__(
        self, coordinator: BluesoundCoordinator, player: Player, port: int
    ) -> None:
        """Initialize the Bluesound button."""
        super().__init__(coordinator)
        sync_status = coordinator.data.sync_status

        self._player = player
        self._attr_unique_id = (
            f"set-sleep-timer-{format_unique_id(sync_status.mac, port)}"
        )
        self._attr_name = f"{sync_status.name} Set Sleep Timer"
        self._attr_device_info = generate_device_info(sync_status, port)
        self._attr_entity_registry_enabled_default = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_available = self.coordinator.data.is_online
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Set the sleep timer."""
        await self._player.sleep_timer()


class ClearSleepTimerButton(CoordinatorEntity[BluesoundCoordinator], ButtonEntity):
    """Representation of a sleep timer button."""

    def __init__(
        self, coordinator: BluesoundCoordinator, player: Player, port: int
    ) -> None:
        """Initialize the Bluesound button."""
        super().__init__(coordinator)
        sync_status = coordinator.data.sync_status

        self._player = player
        self._attr_unique_id = (
            f"clear-sleep-timer-{format_unique_id(sync_status.mac, port)}"
        )
        self._attr_name = f"{sync_status.name} Clear Sleep Timer"
        self._attr_device_info = generate_device_info(sync_status, port)
        self._attr_entity_registry_enabled_default = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_available = self.coordinator.data.is_online
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Clear the sleep timer."""
        sleep = -1
        while sleep != 0:
            sleep = await self._player.sleep_timer()
