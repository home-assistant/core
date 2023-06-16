"""Platform for sensor integration."""
from __future__ import annotations

from trello import TrelloClient

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrelloDataUpdateCoordinator


class TrelloSensor(CoordinatorEntity[TrelloDataUpdateCoordinator], SensorEntity):
    """Representation of a TrelloSensor."""

    _attr_native_unit_of_measurement: str | None = "Cards"
    _attr_state_class: SensorStateClass | str | None = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        board: dict,
        _list: dict[str, str],
        coordinator: TrelloDataUpdateCoordinator,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.board = board
        self.list_id = _list["id"]
        self.coordinator = coordinator
        self._attr_unique_id = f"list_{self.list_id}".lower()
        self._attr_name = _list["name"]
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> int:
        """Return the card count of the sensor's list."""
        return self.coordinator.data[self.list_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.board["id"])},
            name=self.board["name"],
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Trello",
            model="Board",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trello sensors for config entries."""
    boards = config_entry.options["boards"]
    if not boards:
        return
    config_data = config_entry.data
    trello_client = TrelloClient(
        api_key=config_data["api_key"], api_secret=config_data["api_token"]
    )
    coordinator = TrelloDataUpdateCoordinator(hass, trello_client, list(boards.keys()))
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            TrelloSensor(board, list_, coordinator)
            for board in boards.values()
            for list_ in board["lists"]
        ],
        True,
    )
