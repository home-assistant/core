"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from kasa import (
    AuthenticationException,
    EmeterStatus,
    SmartDevice,
    SmartDeviceException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35


class TPLinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a specific TPLink device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: SmartDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.device = device
        self.has_emeter = device.has_emeter
        super().__init__(
            hass,
            _LOGGER,
            name=device.host,
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        device = self.device
        try:
            await device.update(update_children=False)
        except AuthenticationException as ex:
            raise ConfigEntryAuthFailed from ex
        except SmartDeviceException as ex:
            raise UpdateFailed(ex) from ex
        if self.has_emeter:
            try:  # noqa: SIM105 - suppress is much slower
                del self.emeter_realtime
            except AttributeError:
                pass

    @cached_property
    def emeter_realtime(self) -> EmeterStatus | None:
        """Return cached emeter_realtime.

        Multiple sensors build this object every time we write state
        to the state machine. Since its the same object until the
        next update, we can cache it.
        """
        if not self.has_emeter:
            return None
        return self.device.emeter_realtime  # type: ignore[no-any-return]
