"""Platform for the opengarage.io cover component."""

import logging
from typing import Any, cast
from urllib.parse import urlencode

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_KEY
from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
from .entity import OpenGarageEntity

_LOGGER = logging.getLogger(__name__)

STATES_MAP = {
    0: CoverState.CLOSED,
    1: CoverState.OPEN,
    2: CoverState.OPEN,  # stopped (partially open)
    3: CoverState.CLOSING,
    4: CoverState.OPENING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenGarage covers."""
    async_add_entities(
        [OpenGarageCover(entry.runtime_data, cast(str, entry.unique_id))]
    )


class OpenGarageCover(OpenGarageEntity, CoverEntity):
    """Representation of a OpenGarage cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self, coordinator: OpenGarageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the cover."""
        self._state: str | None = None
        self._state_before_move: str | None = None

        super().__init__(coordinator, device_id)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state == CoverState.CLOSED

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._state is None:
            return None
        return self._state == CoverState.CLOSING

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._state is None:
            return None
        return self._state == CoverState.OPENING

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._state in [CoverState.CLOSED, CoverState.CLOSING]:
            return
        self._state_before_move = self._state
        self._state = CoverState.CLOSING
        self.async_write_ha_state()
        await self._push_close_button()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._state in [CoverState.OPEN, CoverState.OPENING]:
            return
        self._state_before_move = self._state
        self._state = CoverState.OPENING
        self.async_write_ha_state()
        await self._push_open_button()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""
        status = self.coordinator.data

        state = STATES_MAP.get(status.get("door"))  # type: ignore[arg-type]
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

    async def _push_close_button(self) -> None:
        """Send a close command to the API."""
        await self._push_button("close")

    async def _push_open_button(self) -> None:
        """Send an open command to the API."""
        await self._push_button("open")

    async def _push_button(self, command: str) -> None:
        """Send commands to API."""
        params = {
            "dkey": self.coordinator.config_entry.data[CONF_DEVICE_KEY],
            command: "1",
        }
        data = await self.coordinator.open_garage_connection._execute(  # noqa: SLF001
            f"cc?{urlencode(params)}"
        )
        if not isinstance(data, dict):
            _LOGGER.error(
                "Unable to control %s: Invalid API response: %r", self.name, data
            )
            self._revert_state()
            return

        result = data.get("result")
        if isinstance(result, int):
            if result == 1:
                return

            if result == 2:
                _LOGGER.error(
                    "Unable to control %s: Device key is incorrect", self.name
                )
            else:
                _LOGGER.error(
                    "Unable to control %s: Error code %s (response: %r)",
                    self.name,
                    result,
                    data,
                )
        else:
            _LOGGER.error(
                "Unable to control %s: Invalid API result: %r (response: %r)",
                self.name,
                result,
                data,
            )

        self._revert_state()

    def _revert_state(self) -> None:
        """Revert the optimistic state after a failed command."""
        if self._state_before_move is None:
            _LOGGER.warning(
                "Unable to revert state for %s: no previous state was saved", self.name
            )
            return

        self._state = self._state_before_move
        self._state_before_move = None
        self.async_write_ha_state()
