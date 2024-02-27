"""Data coordinators for the ring integration."""
from asyncio import TaskGroup
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Optional

import ring_doorbell
from ring_doorbell.generic import RingGeneric

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NOTIFICATIONS_SCAN_INTERVAL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def _call_api(
    hass: HomeAssistant, target: Callable[..., Any], *args, msg_suffix: str = ""
):
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
        ring_api: ring_doorbell.Ring,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            name="devices",
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )
        self.ring_api: ring_doorbell.Ring = ring_api
        self.first_call: bool = True

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        update_method: str = "update_data" if self.first_call else "update_devices"
        await _call_api(self.hass, getattr(self.ring_api, update_method))
        self.first_call = False
        data: dict[str, RingDeviceData] = {}
        devices: dict[str : list[RingGeneric]] = self.ring_api.devices()
        subscribed_device_ids = set(self.async_contexts())
        for device_type in devices:
            for device in devices[device_type]:
                # Don't update all devices in the ring api, only those that set
                # their device id as context when they subscribed.
                if device.id in subscribed_device_ids:
                    data[device.id] = RingDeviceData(device=device)
                    try:
                        history_task = None
                        async with TaskGroup() as tg:
                            if device.has_capability("history"):
                                history_task = tg.create_task(
                                    _call_api(
                                        self.hass,
                                        lambda device: device.history(limit=10),
                                        device,
                                        msg_suffix=f" for device {device.name}",  # device_id is the mac
                                    )
                                )
                            tg.create_task(
                                _call_api(
                                    self.hass,
                                    device.update_health_data,
                                    msg_suffix=f" for device {device.name}",
                                )
                            )
                        if history_task:
                            data[device.id].history = history_task.result()
                    except ExceptionGroup as eg:
                        raise eg.exceptions[0]  # noqa: B904

        return data


class RingNotificationsCoordinator(DataUpdateCoordinator[None]):
    """Global notifications coordinator."""

    def __init__(self, hass: HomeAssistant, ring_api: ring_doorbell.Ring) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="active dings",
            update_interval=NOTIFICATIONS_SCAN_INTERVAL,
        )
        self.ring_api: ring_doorbell.Ring = ring_api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        await _call_api(self.hass, self.ring_api.update_dings)
