"""The cover entity of reisinger intellidrive."""

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import ReisingerSlidingDoorDevice

_LOGGER = logging.getLogger(__name__)


class SlidingDoorEntityWrapper(CoverEntity):
    """Wrapper class to adapt the Meross Garage Opener into the Homeassistant platform."""

    _device: ReisingerSlidingDoorDevice

    def __init__(
        self,
        host: str,
        token: str,
        device: ReisingerSlidingDoorDevice,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize entitywrapper."""
        self._host = host
        self._token = token
        self._device = device
        self._coordinator = coordinator

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
