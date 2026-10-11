"""Philips TV menu select entities."""

from typing import override

from haphilipsjs.typing import (
    MenuItemsSettingsNode,
    MenuItemsSettingsUpdateValueData,
    MenuItemsSettingsValueEnum,
    MenuItemsSettingsValueNode,
)

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PhilipsTVConfigEntry, PhilipsTVDataUpdateCoordinator
from .entity import PhilipsTVSettingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PhilipsTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = config_entry.runtime_data

    entities: list[Entity] = []
    for data in coordinator.settings_nodes:
        if data["node"]["type"] == "PARENT_NODE":
            entities.append(
                PhilipsTVParentNode(coordinator, data["node"], data["name"])
            )

        if data["node"]["type"] == "LIST_NODE":
            entities.append(PhilipsTVListNode(coordinator, data["node"], data["name"]))

    async_add_entities(entities)


class PhilipsTVListNode(PhilipsTVSettingsEntity, SelectEntity):
    """A Philips TV menu settings switch."""

    _data: MenuItemsSettingsValueEnum | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, node, name)
        self._options: dict[int, str] = {}
        self._options_reversed: dict[str, int] = {}
        self._attr_options = []

    @override
    def _get_coordinator_data(self) -> None:
        """Get the data from the coordinator on update."""
        super()._get_coordinator_data()
        if self._data:
            self._options = {
                enum["enum_id"]: self.coordinator.get_string(enum["string_id"])
                for enum in self._data.get("enum_values", [])
                if enum["available"]
            }
        else:
            self._options = {}

        self._options_reversed = {value: key for key, value in self._options.items()}
        self._attr_options = list(self._options.values())

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if (
            self._data
            and (selected_item := self._data.get("selected_item")) is not None
        ):
            return self._options.get(selected_item)
        return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (selected_item := self._options_reversed.get(option)) is None:
            raise HomeAssistantError(f"Invalid option: {option}")

        data: dict[int, MenuItemsSettingsUpdateValueData] = {
            self._node["node_id"]: {"select_item": selected_item}
        }
        await self.coordinator.api.postMenuItemsSettingsUpdateData(data)
        await self.coordinator.async_request_refresh()


class PhilipsTVParentNode(PhilipsTVSettingsEntity, SelectEntity):
    """A Philips TV menu settings switch."""

    _data: MenuItemsSettingsValueNode | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, node, name)
        self._options: dict[int, str] = {}
        self._options_reversed: dict[str, int] = {}
        self._update_options()

    def _update_options(self) -> None:
        """Calculate the options from the translated names of the child nodes."""
        self._options = {
            child["node_id"]: self.coordinator.get_string(string_id)
            for child in self._node["data"].get("nodes", {})
            if (string_id := child.get("string_id"))
        }
        self._options_reversed = {value: key for key, value in self._options.items()}
        self._attr_options = list(self._options.values())

    @override
    def _get_coordinator_data(self) -> None:
        """Get the data from the coordinator on update."""
        super()._get_coordinator_data()
        self._update_options()

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if not self._data:
            return None
        selected_item = self._data.get("activenode_id")
        if selected_item is None:
            return None
        return self._options.get(selected_item)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        selected_item = self._options_reversed.get(option)
        if selected_item is None:
            raise HomeAssistantError(f"Invalid option: {option}")

        data: dict[int, MenuItemsSettingsUpdateValueData] = {
            self._node["node_id"]: {"activenode_id": selected_item}
        }
        await self.coordinator.api.postMenuItemsSettingsUpdateData(data)
        await self.coordinator.async_request_refresh()
