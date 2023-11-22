"""Data coordinators for the ring integration."""
from dataclasses import dataclass
import logging
from typing import Optional

import ring_doorbell
from ring_doorbell.generic import RingGeneric

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NOTIFICATIONS_SCAN_INTERVAL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def _call_api(hass: HomeAssistant, target, *args, msg_suffix=""):
    try:
        return await hass.async_add_executor_job(target, *args)
    except ring_doorbell.AuthenticationError as err:
        # Raising ConfigEntryAuthFailed will cancel future updates
        # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        raise ConfigEntryAuthFailed from err
    except ring_doorbell.RingTimeout as err:
        raise UpdateFailed(
            f"Timeout communicating with API{msg_suffix}: {err}"
        ) from err
    except ring_doorbell.RingError as err:
        raise UpdateFailed(f"Error communicating with API{msg_suffix}: {err}") from err


@dataclass
class RingDeviceData:
    """RingDeviceData."""

    device: RingGeneric
    history: Optional[list] = None


class RingDataCoordinator(DataUpdateCoordinator[dict[int, RingDeviceData]]):
    """Base class for device coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        ring_api,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            name="devices",
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )
        self.ring_api = ring_api
        self.first_call = True

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        update_method = "update_data" if self.first_call else "update_devices"
        await _call_api(self.hass, getattr(self.ring_api, update_method))
        self.first_call = False
        data = {}
        devices = self.ring_api.devices()
        for device_type in devices:
            for device in devices[device_type]:
                # Don't update all devices in the ring api, only those that set
                # their device id as context when they subscribed.
                if device.id in set(self.async_contexts()):
                    data[device.id] = RingDeviceData(device=device)
                    if hasattr(device, "history"):
                        data[device.id].history = await _call_api(
                            self.hass,
                            lambda device: device.history(limit=10),
                            device,
                            msg_suffix=f" for device {device.name}",  # device_id is the mac
                        )
                    await _call_api(
                        self.hass,
                        device.update_health_data,
                        msg_suffix=f" for device {device.name}",
                    )
        return data


class RingNotificationsCoordinator(DataUpdateCoordinator[None]):
    """Global notifications coordinator."""

    def __init__(self, hass: HomeAssistant, ring_api) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="active dings",
            update_interval=NOTIFICATIONS_SCAN_INTERVAL,
        )
        self.ring_api = ring_api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        await _call_api(self.hass, self.ring_api.update_dings)
