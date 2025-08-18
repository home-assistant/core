"""Cover platform for Vitrea integration."""

from __future__ import annotations

import logging
from typing import Any

from vitreaclient.client import VitreaClient
from vitreaclient.constants import DeviceStatus, VitreaResponse

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,  # pylint: disable=hass-argument-type
) -> None:
    """Set up cover entities from a config entry."""
    if len(entry.runtime_data.covers) > 0:
        _LOGGER.debug("Adding %d new covers entities", len(entry.runtime_data.covers))
        async_add_entities(entry.runtime_data.covers)

    entry.runtime_data.client.on(
        VitreaResponse.STATUS, lambda data: _handle_cover_event(entry, data)
    )


def _handle_cover_event(entry: ConfigEntry, event: Any) -> None:
    """Handle cover events from Vitrea client."""
    if event.status != DeviceStatus.BLIND:
        return

    _LOGGER.debug("Handling cover status: %s", event)
    position = event.data
    entity_id = f"{event.node}_{event.key}"
    entity: VitreaCover | None = None

    for cover in entry.runtime_data.covers:
        if cover.unique_id == entity_id:
            entity = cover
            break

    if entity:
        _LOGGER.debug("Updating state for %s to %s", entity_id, position)
        entity.set_position(int(position))
        entity.async_write_ha_state()

    else:
        _LOGGER.warning("Received status for cover entity %s not found", entity_id)


class VitreaCover(CoverEntity):
    """Representation of a Vitrea cover."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_has_entity_name = True

    def __init__(
        self, node: str, key: str, position: str, monitor: VitreaClient
    ) -> None:
        """Initialize the cover."""
        self.monitor = monitor
        self._node = node
        self._key = key
        self._attr_unique_id = f"{node}_{key}"
        self._attr_current_cover_position = int(position)
        self._target_position = int(position)
        self._initial_position = int(position)
        self._is_opening = False
        self._is_closing = False

        # Modern naming pattern with device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node)},
            name=f"Vitrea Node {node}",
            manufacturer="Vitrea",
        )

        # For specific blinds/covers, use descriptive names
        self._attr_name = f"Blind {key}"  # e.g., "Blind 1", "Blind bedroom"

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._attr_current_cover_position == 0

    @property
    def is_open(self) -> bool:
        """Return if the cover is open."""
        return self._attr_current_cover_position == 100

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        return False

    @property
    def assumed_state(self) -> bool:
        """Return if the state is assumed."""
        return True

    def set_position(self, position: int) -> None:
        """Set the cover position."""
        self._attr_current_cover_position = position
        self._target_position = position
        self._initial_position = position
        self._is_opening = False
        self._is_closing = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.debug("open_cover %s/%s", self._node, self._key)

        try:
            self._attr_current_cover_position = 100
            self._target_position = 100
            self._is_opening = True
            self._is_closing = False
            await self.monitor.blind_open(self._node, self._key)

        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to open cover %s/%s: %s", self._node, self._key, err)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.debug("close_cover %s/%s", self._node, self._key)

        try:
            self._attr_current_cover_position = 0
            self._target_position = 0
            self._is_opening = False
            self._is_closing = True
            await self.monitor.blind_close(self._node, self._key)

        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to close cover %s/%s: %s", self._node, self._key, err)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        _LOGGER.debug("set_cover_position %s/%s: %s", self._node, self._key, kwargs)
        position = kwargs.get("position")
        if position is not None:
            _LOGGER.debug("cover_position %s/%s", self._node, self._key)
            try:
                self._target_position = position
                self._attr_current_cover_position = position
                self._is_opening = position > self._initial_position
                self._is_closing = position < self._initial_position
                await self.monitor.blind_percent(self._node, self._key, position)

            except (OSError, TimeoutError) as err:
                _LOGGER.error(
                    "Failed to set cover position %s/%s: %s", self._node, self._key, err
                )

        else:
            _LOGGER.error("Cover_position missing POSITION value")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self.monitor.blind_stop(self._node, self._key)
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Failed to stop cover %s/%s: %s", self._node, self._key, err)
