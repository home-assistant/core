"""Philips TV menu switches."""

from typing import override

from haphilipsjs.typing import (
    MenuItemsSettingsNode,
    MenuItemsSettingsNodeDataSlider,
    MenuItemsSettingsNodeDataSliderData,
    MenuItemsSettingsUpdateValueData,
    MenuItemsSettingsValueSlider,
    MenuItemsSettingsValueSliders,
)

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
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
        node = data["node"]
        if node["type"] == "SLIDER_NODE":
            node_data = node["data"]
            entities.append(
                PhilipsTVSingleSlider(
                    coordinator, data["node"], node_data["slider_data"], data["name"]
                )
            )

        if data["node"]["type"] == "MULTIPLE_SLIDER":
            entities.extend(
                PhilipsTVMultiSlider(
                    coordinator,
                    data["node"],
                    slider,
                    data["name"] + " / " + coordinator.get_string(slider["slider_id"]),
                )
                for slider in data["node"]["data"]["sliders"]
            )
    async_add_entities(entities)


class PhilipsTVSingleSlider(PhilipsTVSettingsEntity, NumberEntity):
    """A Philips TV menu settings switch."""

    _data: MenuItemsSettingsValueSlider | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        slider_data: MenuItemsSettingsNodeDataSliderData,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, node, name)

        self._attr_native_min_value = slider_data["min"]
        self._attr_native_max_value = slider_data["max"]
        self._attr_native_step = slider_data["step_size"]
        self._attr_mode = NumberMode.SLIDER

    @property
    @override
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""

        if not self._data:
            return None

        return float(self._data["value"])

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        data: dict[int, MenuItemsSettingsUpdateValueData] = {
            self._node["node_id"]: {"value": int(value)}
        }
        await self.coordinator.api.postMenuItemsSettingsUpdateData(data)
        await self.coordinator.async_request_refresh()


class PhilipsTVMultiSlider(PhilipsTVSettingsEntity, NumberEntity):
    """A Philips TV menu settings switch."""

    _data: MenuItemsSettingsValueSliders | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        slider: MenuItemsSettingsNodeDataSlider,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, node, name)

        self._slider_id = slider["slider_id"]
        self._attr_unique_id += "_" + self._slider_id
        self._attr_native_min_value = slider["slider_data"]["min"]
        self._attr_native_max_value = slider["slider_data"]["max"]
        self._attr_native_step = slider["slider_data"].get("step_size", 1)
        self._attr_mode = NumberMode.SLIDER

    @property
    @override
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""

        if not self._data:
            return None

        for value in self._data["values"]:
            if value["slider_id"] == self._slider_id:
                return float(value["value"])

        return None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        data: dict[int, MenuItemsSettingsUpdateValueData] = {
            self._node["node_id"]: {"value": int(value), "slider_id": self._slider_id}
        }
        await self.coordinator.api.postMenuItemsSettingsUpdateData(data)
        await self.coordinator.async_request_refresh()
