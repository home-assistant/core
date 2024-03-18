"""Sensor platform for Trello integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrelloDataUpdateCoordinator
from .models import Board, List


class TrelloSensor(CoordinatorEntity[TrelloDataUpdateCoordinator], SensorEntity):
    """Representation of a TrelloSensor."""

    _attr_native_unit_of_measurement = "Cards"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        board: Board,
        list_: List,
        coordinator: TrelloDataUpdateCoordinator,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.board = board
        self.list_id = list_.id
        self._attr_unique_id = f"list_{list_.id}".lower()
        self._attr_name = list_.name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, board.id)},
            name=board.name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Trello",
            model="Board",
        )

    @property
    def available(self) -> bool:
        """Determine if sensor is available."""
        if not super().available:
            return False
        board = self.coordinator.data[self.board.id]
        return bool(board.lists and board.lists.get(self.list_id))

    @property
    def native_value(self) -> int | None:
        """Return the card count of the sensor's list."""
        return self.coordinator.data[self.board.id].lists[self.list_id].card_count

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.available:
            board = self.coordinator.data[self.board.id]
            self._attr_name = board.lists[self.list_id].name
            self.async_write_ha_state()
        super()._handle_coordinator_update()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trello sensors for config entries."""
    trello_coordinator: TrelloDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    boards = trello_coordinator.data.values()

    async_add_entities(
        [
            TrelloSensor(board, list_, trello_coordinator)
            for board in boards
            for list_ in board.lists.values()
        ],
        True,
    )
