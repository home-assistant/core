"""An abstract class common to all Bond entities."""
from abc import abstractmethod
from asyncio import TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from aiohttp import ClientError
from bond_api import BPUPSubscriptions

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)

_FALLBACK_SCAN_INTERVAL = timedelta(seconds=10)


class BondEntity(Entity):
    """Generic Bond entity encapsulating common features of any Bond controlled device."""

    def __init__(
        self,
        hub: BondHub,
        device: BondDevice,
        bpup_subs: BPUPSubscriptions,
        sub_device: Optional[str] = None,
    ):
        """Initialize entity with API and device info."""
        self._hub = hub
        self._device = device
        self._sub_device = sub_device
        self._available = True
        self._bpup_subs = bpup_subs
        self._cancel_updates = None

    @property
    def unique_id(self) -> Optional[str]:
        """Get unique ID for the entity."""
        hub_id = self._hub.bond_id
        device_id = self._device.device_id
        sub_device_id: str = f"_{self._sub_device}" if self._sub_device else ""
        return f"{hub_id}_{device_id}{sub_device_id}"

    @property
    def name(self) -> Optional[str]:
        """Get entity name."""
        return self._device.name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Get a an HA device representing this Bond controlled device."""
        return {
            ATTR_NAME: self.name,
            "identifiers": {(DOMAIN, self._device.device_id)},
            "via_device": (DOMAIN, self._hub.bond_id),
        }

    @property
    def assumed_state(self) -> bool:
        """Let HA know this entity relies on an assumed state tracked by Bond."""
        return self._hub.is_bridge and not self._device.trust_state

    @property
    def available(self) -> bool:
        """Report availability of this entity based on last API call results."""
        return self._available

    async def async_update(self):
        """Fetch assumed state of the cover from the hub using API."""
        await self._async_update_from_api()

    async def _async_update_if_bpup_not_alive(self, now):
        """Fetch via the API if BPUP is not alive."""
        if self._bpup_subs.alive:
            return
        await self._async_update_from_api()
        self.async_write_ha_state()

    async def _async_update_from_api(self):
        """Fetch via the API."""
        try:
            state: dict = await self._hub.bond.device_state(self._device.device_id)
        except (ClientError, AsyncIOTimeoutError, OSError) as error:
            if self._available:
                _LOGGER.warning(
                    "Entity %s has become unavailable", self.entity_id, exc_info=error
                )
            self._available = False
        else:
            _LOGGER.debug("Device state for %s is:\n%s", self.entity_id, state)
            if not self._available:
                _LOGGER.info("Entity %s has come back", self.entity_id)
            self._available = True
            self._apply_state(state)

    @abstractmethod
    def _apply_state(self, state: dict):
        raise NotImplementedError

    def _bpup_callback(self, state):
        """Process a BPUP state change."""
        self._available = True
        self._apply_state(state)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to BPUP."""
        await super().async_added_to_hass()
        self._bpup_subs.subscribe(self._device.device_id, self._bpup_callback)
        self._cancel_updates = async_track_time_interval(
            self.hass, self._async_update_if_bpup_not_alive, _FALLBACK_SCAN_INTERVAL
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from BPUP data on remove."""
        await super().async_will_remove_from_hass()
        self._bpup_subs.unsubscribe(self._device.device_id, self._bpup_callback)
        if self._cancel_updates:
            self._cancel_updates()
            self._cancel_updates = None
