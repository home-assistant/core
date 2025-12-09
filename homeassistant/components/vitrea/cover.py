"""Cover platform for Vitrea integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VitreaCoordinator
from .models import VitreaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitreaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover entities from a config entry."""
    coordinator = entry.runtime_data

    # Add initial entities discovered during setup
    # entities = []
    # cover_entities = coordinator.get_entities_by_platform("cover")
    # for entity_id, data in cover_entities.items():
    #     entities.append(VitreaCover(coordinator, entity_id, data))
    #
    # if entities:
    #     _LOGGER.debug("Adding %d initial cover entities", len(entities))
    #     async_add_entities(entities)

    # Set up callback for dynamic entity discovery for cover platform
    def add_new_cover_entity(entity_id: str, data: dict[str, Any]) -> None:
        """Add a new cover entity discovered after setup."""
        _LOGGER.info("Adding new cover entity: %s", entity_id)
        new_entity = VitreaCover(coordinator, entity_id, data)
        async_add_entities([new_entity])

    coordinator.set_entity_add_callback("cover", add_new_cover_entity)


class VitreaCover(CoordinatorEntity[VitreaCoordinator], CoverEntity):
    """Representation of a Vitrea cover."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self, coordinator: VitreaCoordinator, entity_id: str, data: dict[str, Any]
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)

        self._entity_id = entity_id
        self._node = data["node"]
        self._key = data["key"]
        self._attr_unique_id = entity_id

        # Modern naming pattern with device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._node)},
            name=f"Node {self._node}",
            manufacturer="Vitrea",
        )

        # For specific blinds/covers, use descriptive names
        self._attr_name = f"Blind {self._key}"  # e.g., "Blind 1", "Blind bedroom"

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self.coordinator.data and self._entity_id in self.coordinator.data:
            return self.coordinator.data[self._entity_id]["position"]
        return None

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        position = self.current_cover_position
        return position == 0 if position is not None else False

    @property
    def is_open(self) -> bool:
        """Return if the cover is open."""
        position = self.current_cover_position
        return position == 100 if position is not None else False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.debug("open_cover %s/%s", self._node, self._key)

        try:
            await self.coordinator.client.blind_open(self._node, self._key)
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to open cover %s/%s: %s", self._node, self._key, err)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.debug("close_cover %s/%s", self._node, self._key)

        try:
            await self.coordinator.client.blind_close(self._node, self._key)
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to close cover %s/%s: %s", self._node, self._key, err)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        position = kwargs.get("position")
        if position is None:
            _LOGGER.error("Cover position missing POSITION value")
            return

        _LOGGER.debug("set_cover_position %s/%s: %s", self._node, self._key, position)

        try:
            await self.coordinator.client.blind_percent(self._node, self._key, position)
        except (OSError, TimeoutError) as err:
            _LOGGER.error(
                "Failed to set cover position %s/%s: %s", self._node, self._key, err
            )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self.coordinator.client.blind_stop(self._node, self._key)
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to stop cover %s/%s: %s", self._node, self._key, err)
