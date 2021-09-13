"""Support for Bouygues Bbox."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .router import BboxCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the switch."""
    router = hass.data[DOMAIN][entry.unique_id]
    async_add_entities([BboxWifiSwitch(router)], True)


class BboxWifiSwitch(SwitchEntity):
    """Representation of a Bbox wifi switch."""

    def __init__(self, router: BboxCoordinator) -> None:
        """Initialize the Wifi switch."""
        self._name = "Bbox WiFi"
        self._router = router
        self._unique_id = f"{router.entry_id}_{self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    async def _async_set_state(self, enabled: bool):
        """Turn the switch on or off."""
        self._router.set_wifi(enabled)

        # try:
        # box_info = await self.hass.async_add_executor_job(
        #     bbox_request_raising, self.bbox, BboxApiEndpoints.get_bbox_info
        # )
        # try:
        #     await self._router.wifi.set_global_config(wifi_config)
        # except InsufficientPermissionsError:
        #     _LOGGER.warning(
        #         "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation"
        #     )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._async_set_state(False)

    async def async_update(self):
        """Get the state and update it."""
        state = await self._router.data["wifi_enabled"]
        self._state = bool(state)
