"""The cover entity of reisinger intellidrive."""

import logging
from typing import Any, cast

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_TOKEN,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATUSDICT_OPENSTATE, STATUSDICT_SERIALNO
from .coordinator import ReisingerCoordinator
from .entity import IntelliDriveEntity

_LOGGER = logging.getLogger(__name__)

STATES_MAP = {0: STATE_CLOSED, 1: STATE_OPEN}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Intellidrive covers."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            SlidingDoorCoverEntity(
                hass,
                coordinator,
                entry.data[CONF_HOST],
                str(entry.data.get(CONF_TOKEN)),
                cast(str, entry.unique_id),
            )
        ]
    )


class SlidingDoorCoverEntity(IntelliDriveEntity, CoverEntity):
    """Wrapper class to adapt the intellidrive device into the Homeassistant platform."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ReisingerCoordinator,
        host: str,
        token: str,
        device_id: str,
    ) -> None:
        """Initialize slidingdoor cover."""
        self._state: str | None = None
        self._state_before_move: str | None = None
        self._host = host
        self._token = token
        self._device_api = coordinator.device
        super().__init__(coordinator, device_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door async."""

        if self._state in [STATE_CLOSED, STATE_CLOSING]:
            return
        self._state_before_move = self._state
        self._state = STATE_CLOSING

        await self._device_api.async_close()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door async."""

        if self._state in [STATE_OPEN, STATE_OPENING]:
            return
        self._state_before_move = self._state
        self._state = STATE_OPENING

        await self._device_api.async_open()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the door async."""
        await self._device_api.async_stop_door()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the door."""
        self.hass.async_add_executor_job(self.async_stop_cover, **kwargs)

    def open_cover(self, **kwargs: Any) -> None:
        """Open the door."""
        self.hass.async_add_executor_job(self.async_open_cover, **kwargs)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the door."""
        self.hass.async_add_executor_job(self.async_close_cover, **kwargs)

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the class of this device."""
        return CoverDeviceClass.DOOR

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""

        status = self.coordinator.data
        self._attr_name = f"Slidingdoor {status[STATUSDICT_SERIALNO]}"

        state = STATES_MAP.get(status.get(STATUSDICT_OPENSTATE))
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

        if self._state is None:
            return None
        return self._state == STATE_CLOSED

    @property
    def is_closing(self) -> bool | None:
        """Get state if the door is closing now."""
        if self._state is None:
            return None
        return self._state == STATE_CLOSING

    @property
    def is_opening(self) -> bool | None:
        """Get state if the door is opening now."""
        if self._state is None:
            return None
        return self._state == STATE_OPENING
