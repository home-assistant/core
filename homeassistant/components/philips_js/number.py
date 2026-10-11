"""Philips TV menu settings exposed as numbers."""

from dataclasses import dataclass
import logging
from typing import override

from haphilipsjs import ConnectionFailure, GeneralFailure
from haphilipsjs.typing import MenuItemsSettingsNode

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TV_STATE_ON
from .coordinator import PhilipsTVConfigEntry, PhilipsTVDataUpdateCoordinator
from .entity import PhilipsJsEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SLIDER_NODE = "SLIDER_NODE"


@dataclass(frozen=True, kw_only=True)
class PhilipsTVNumberEntityDescription(NumberEntityDescription):
    """Describes a Philips TV menu slider.

    The node id of a menu item differs between models and firmwares,
    so the slider is looked up using its context in the menu structure.
    """

    context: str


NUMBER_DESCRIPTIONS: tuple[PhilipsTVNumberEntityDescription, ...] = (
    PhilipsTVNumberEntityDescription(
        key="contrast",
        context="contrast",
        translation_key="contrast",
    ),
    PhilipsTVNumberEntityDescription(
        key="brightness",
        context="brightness",
        translation_key="black_level",
    ),
    PhilipsTVNumberEntityDescription(
        key="video_contrast",
        context="video_contrast",
        translation_key="video_contrast",
    ),
    PhilipsTVNumberEntityDescription(
        key="colour",
        context="colour",
        translation_key="colour",
    ),
    PhilipsTVNumberEntityDescription(
        key="sharpness",
        context="sharpness",
        translation_key="sharpness",
    ),
    PhilipsTVNumberEntityDescription(
        key="gamma",
        context="gamma",
        translation_key="gamma",
    ),
    PhilipsTVNumberEntityDescription(
        key="ambilight_brightness",
        context="ambilight_brightness",
        translation_key="ambilight_brightness",
    ),
)


def _find_slider_nodes(
    node: MenuItemsSettingsNode, contexts: set[str]
) -> dict[str, MenuItemsSettingsNode]:
    """Find the first slider node for each wanted context in the menu tree."""
    found: dict[str, MenuItemsSettingsNode] = {}
    if node.get("type") == SLIDER_NODE and (context := node.get("context")):
        if context in contexts and "slider_data" in node["data"]:
            found[context] = node
    for child in node["data"].get("nodes", []):
        for context, child_node in _find_slider_nodes(child, contexts).items():
            found.setdefault(context, child_node)
    return found


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PhilipsTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = config_entry.runtime_data
    added: set[str] = set()

    async def _async_add_new_entities() -> None:
        """Add the sliders found in the menu structure of the TV."""
        if not (settings := coordinator.api.settings) or "node" not in settings:
            return

        descriptions = [d for d in NUMBER_DESCRIPTIONS if d.key not in added]
        nodes = _find_slider_nodes(settings["node"], {d.context for d in descriptions})
        entities = [
            PhilipsTVNumber(coordinator, description, nodes[description.context])
            for description in descriptions
            if description.context in nodes
        ]
        if not entities:
            return

        added.update(entity.entity_description.key for entity in entities)
        coordinator.menu_node_ids.update(entity.node_id for entity in entities)
        try:
            await coordinator.async_update_menu_values()
        except ConnectionFailure, GeneralFailure:
            _LOGGER.debug("Unable to fetch the menu settings of the TV")
        async_add_entities(entities)

    await _async_add_new_entities()

    @callback
    def _async_coordinator_updated() -> None:
        # The menu structure is only available once the TV has been on
        config_entry.async_create_task(hass, _async_add_new_entities())

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_coordinator_updated)
    )


class PhilipsTVNumber(PhilipsJsEntity, NumberEntity):
    """A slider from the menu settings of a Philips TV."""

    entity_description: PhilipsTVNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        description: PhilipsTVNumberEntityDescription,
        node: MenuItemsSettingsNode,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.node_id = node["node_id"]

        slider = node["data"]["slider_data"]
        self._attr_native_min_value = slider["min"]
        self._attr_native_max_value = slider["max"]
        self._attr_native_step = slider["step_size"]
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def _menu_value(self):
        """Return the last fetched menu value."""
        return self.coordinator.menu_values.get(self.node_id)

    @property
    @override
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        if self.coordinator.api.powerstate not in (TV_STATE_ON, None):
            return False
        if (value := self._menu_value) is None:
            return False
        return value["Available"] and value["Controllable"]

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        if (value := self._menu_value) is None:
            return None
        return value["data"].get("value")

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.api.postMenuItemsSettingsUpdateData(
            {self.node_id: {"value": int(value)}}
        )
        await self.coordinator.async_request_refresh()
