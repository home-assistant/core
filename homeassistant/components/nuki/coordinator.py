"""Coordinator for the nuki component."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import timedelta
import logging

from pynuki import NukiBridge, NukiLock, NukiOpener
from pynuki.bridge import InvalidCredentialsException
from pynuki.device import NukiDevice
from requests.exceptions import RequestException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ERROR_STATES
from .helpers import parse_id

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class NukiCoordinator(DataUpdateCoordinator[None]):
    """Data Update Coordinator for the Nuki integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        bridge: NukiBridge,
        locks: list[NukiLock],
        openers: list[NukiOpener],
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="nuki devices",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=UPDATE_INTERVAL,
        )
        self.bridge = bridge
        self.locks = locks
        self.openers = openers

    @property
    def bridge_id(self):
        """Return the parsed id of the Nuki bridge."""
        return parse_id(self.bridge.info()["ids"]["hardwareId"])

    async def _async_update_data(self) -> None:
        """Fetch data from Nuki bridge."""
        try:
            # Note: TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
                events = await self.hass.async_add_executor_job(
                    self.update_devices, self.locks + self.openers
                )
        except InvalidCredentialsException as err:
            raise UpdateFailed(f"Invalid credentials for Bridge: {err}") from err
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Bridge: {err}") from err

        ent_reg = er.async_get(self.hass)
        for event, device_ids in events.items():
            for device_id in device_ids:
                entity_id = ent_reg.async_get_entity_id(
                    Platform.LOCK, DOMAIN, device_id
                )
                event_data = {
                    "entity_id": entity_id,
                    "type": event,
                }
                self.hass.bus.async_fire("nuki_event", event_data)

    def update_devices(self, devices: list[NukiDevice]) -> dict[str, set[str]]:
        """Update the Nuki devices.

        Returns:
            A dict with the events to be fired. The event type is the key and the device ids are the value

        """

        events: dict[str, set[str]] = defaultdict(set)

        for device in devices:
            for level in (False, True):
                try:
                    if isinstance(device, NukiOpener):
                        last_ring_action_state = device.ring_action_state

                        device.update(level)

                        if not last_ring_action_state and device.ring_action_state:
                            events["ring"].add(device.nuki_id)
                    else:
                        device.update(level)
                except RequestException:
                    continue

                if device.state not in ERROR_STATES:
                    break

        return events
