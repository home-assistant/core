"""Elmax cover platform."""

from __future__ import annotations

import logging
from typing import Any

from elmax_api.model.command import CoverCommand
from elmax_api.model.cover_status import CoverStatus

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElmaxCoordinator
from .common import ElmaxEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_COMMAND_BY_MOTION_STATUS = {  # Maps the stop command to use for every cover motion status
    CoverStatus.DOWN: CoverCommand.DOWN,
    CoverStatus.UP: CoverCommand.UP,
    CoverStatus.IDLE: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elmax cover platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    # Add the cover feature only if supported by the current panel.
    if coordinator.data is None or not coordinator.data.cover_feature:
        return

    known_devices = set()

    def _discover_new_devices():
        if (panel_status := coordinator.data) is None:
            return  # In case the panel is offline, its status will be None. In that case, simply do nothing

        # Otherwise, add all the entities we found
        entities = []
        for cover in panel_status.covers:
            # Skip already handled devices
            if cover.endpoint_id in known_devices:
                continue
            entity = ElmaxCover(
                elmax_device=cover,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            entities.append(entity)

        if entities:
            async_add_entities(entities)
            known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    config_entry.async_on_unload(coordinator.async_add_listener(_discover_new_devices))

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()


class ElmaxCover(ElmaxEntity, CoverEntity):
    """Elmax Cover entity implementation."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __check_cover_status(self, status_to_check: CoverStatus) -> bool | None:
        """Check if the current cover entity is in a specific state."""
        if (
            state := self.coordinator.get_cover_state(self._device.endpoint_id).status
        ) is None:
            return None
        return state == status_to_check

    @property
    def is_closed(self) -> bool | None:
        """Tells if the cover is closed or not."""
        return self.coordinator.get_cover_state(self._device.endpoint_id).position == 0

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self.coordinator.get_cover_state(self._device.endpoint_id).position

    @property
    def is_opening(self) -> bool | None:
        """Tells if the cover is opening or not."""
        return self.__check_cover_status(CoverStatus.UP)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return self.__check_cover_status(CoverStatus.DOWN)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        # To stop the cover, Elmax requires us to re-issue the same command once again.
        # To detect the current motion status, we request an immediate refresh to the coordinator
        await self.coordinator.async_request_refresh()
        motion_status = self.coordinator.get_cover_state(
            self._device.endpoint_id
        ).status
        command = _COMMAND_BY_MOTION_STATUS[motion_status]
        if command:
            await self.coordinator.http_client.execute_command(
                endpoint_id=self._device.endpoint_id, command=command
            )
        else:
            _LOGGER.debug("Ignoring stop request as the cover is IDLE")

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.coordinator.http_client.execute_command(
            endpoint_id=self._device.endpoint_id, command=CoverCommand.UP
        )

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.coordinator.http_client.execute_command(
            endpoint_id=self._device.endpoint_id, command=CoverCommand.DOWN
        )
