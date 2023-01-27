"""The cover entity of reisinger intellidrive."""

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ReisingerCoordinator
from .device import ReisingerSlidingDoorDeviceApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OpenReisinger covers."""
    coordinator = hass.data[DOMAIN]

    async_add_entities(
        [
            SlidingDoorCoverEntity(
                coordinator, str(entry.data.get("host")), str(entry.data.get("token"))
            )
        ]
    )


class SlidingDoorCoverEntity(CoordinatorEntity[ReisingerCoordinator], CoverEntity):
    """Wrapper class to adapt the Meross Garage Opener into the Homeassistant platform."""

    def __init__(
        self,
        coordinator: ReisingerCoordinator,
        host: str,
        token: str,
    ) -> None:
        """Initialize slidingdoor entity."""
        super().__init__(coordinator)
        self._host = host
        self._token = token
        self._device = ReisingerSlidingDoorDeviceApi(host, token)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door async."""
        await self._device.async_close(
            host=self._host, token=self._token, skip_rate_limits=True
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door async."""
        await self._device.async_open(
            host=self._host, token=self._token, skip_rate_limits=True
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the door async."""
        await self._device.async_stop_door(
            host=self._host, token=self._token, skip_rate_limits=True
        )

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

    @property
    def is_closed(self) -> bool:
        """Get state if the door is closed."""

        open_status = self._device.get_is_open(host=self._host, token=self._token)
        return not open_status

    @property
    def is_closing(self) -> bool:
        """Get state if the door is closing now."""

        # Not supported yet
        return False

    @property
    def is_opening(self) -> bool:
        """Get state if the door is opening now."""

        # Not supported yet
        return False
