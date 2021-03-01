"""An abstract class common to all Bond entities."""
from abc import abstractmethod
from asyncio import Lock, TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from aiohttp import ClientError
from bond_api import BPUPSubscriptions

from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
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
        self._device_id = device.device_id
        self._sub_device = sub_device
        self._available = True
        self._bpup_subs = bpup_subs
        self._update_lock = None
        self._initialized = False

    @property
    def unique_id(self) -> Optional[str]:
        """Get unique ID for the entity."""
        hub_id = self._hub.bond_id
        device_id = self._device_id
        sub_device_id: str = f"_{self._sub_device}" if self._sub_device else ""
        return f"{hub_id}_{device_id}{sub_device_id}"

    @property
    def name(self) -> Optional[str]:
        """Get entity name."""
        if self._sub_device:
            sub_device_name = self._sub_device.replace("_", " ").title()
            return f"{self._device.name} {sub_device_name}"
        return self._device.name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Get a an HA device representing this Bond controlled device."""
        device_info = {
            ATTR_NAME: self.name,
            "manufacturer": self._hub.make,
            "identifiers": {(DOMAIN, self._hub.bond_id, self._device.device_id)},
            "suggested_area": self._device.location,
            "via_device": (DOMAIN, self._hub.bond_id),
        }
        if not self._hub.is_bridge:
            device_info["model"] = self._hub.model
            device_info["sw_version"] = self._hub.fw_ver
        else:
            model_data = []
            if self._device.branding_profile:
                model_data.append(self._device.branding_profile)
            if self._device.template:
                model_data.append(self._device.template)
            if model_data:
                device_info["model"] = " ".join(model_data)

        return device_info

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

    async def _async_update_if_bpup_not_alive(self, *_):
        """Fetch via the API if BPUP is not alive."""
        if self._bpup_subs.alive and self._initialized:
            return

        if self._update_lock.locked():
            _LOGGER.warning(
                "Updating %s took longer than the scheduled update interval %s",
                self.entity_id,
                _FALLBACK_SCAN_INTERVAL,
            )
            return

        async with self._update_lock:
            await self._async_update_from_api()
            self.async_write_ha_state()

    async def _async_update_from_api(self):
        """Fetch via the API."""
        try:
            state: dict = await self._hub.bond.device_state(self._device_id)
        except (ClientError, AsyncIOTimeoutError, OSError) as error:
            if self._available:
                _LOGGER.warning(
                    "Entity %s has become unavailable", self.entity_id, exc_info=error
                )
            self._available = False
        else:
            self._async_state_callback(state)

    @abstractmethod
    def _apply_state(self, state: dict):
        raise NotImplementedError

    @callback
    def _async_state_callback(self, state):
        """Process a state change."""
        self._initialized = True
        if not self._available:
            _LOGGER.info("Entity %s has come back", self.entity_id)
        self._available = True
        _LOGGER.debug(
            "Device state for %s (%s) is:\n%s", self.name, self.entity_id, state
        )
        self._apply_state(state)

    @callback
    def _async_bpup_callback(self, state):
        """Process a state change from BPUP."""
        self._async_state_callback(state)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to BPUP and start polling."""
        await super().async_added_to_hass()
        self._update_lock = Lock()
        self._bpup_subs.subscribe(self._device_id, self._async_bpup_callback)
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_update_if_bpup_not_alive, _FALLBACK_SCAN_INTERVAL
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from BPUP data on remove."""
        await super().async_will_remove_from_hass()
        self._bpup_subs.unsubscribe(self._device_id, self._async_bpup_callback)
