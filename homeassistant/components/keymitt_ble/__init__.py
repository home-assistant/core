"""Integration to integrate MicroBot with Home Assistant."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import TYPE_CHECKING, Any
import async_timeout

from microbot import (
    MicroBotApiClient,
    parse_advertisement_data,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BDADDR,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
)

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER: logging.Logger = logging.getLogger(__package__)
PLATFORMS: list[str] = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    bdaddr: Any | None = entry.data.get(CONF_BDADDR)
    assert bdaddr is not None
    ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
        hass, bdaddr.upper()
    )
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find MicroBot with address {bdaddr}")
    conf_dir = hass.config.path()
    conf = (
        conf_dir
        + "/.storage/microbot-"
        + re.sub("[^a-f0-9]", "", bdaddr.lower())
        + ".conf"
    )
    client = MicroBotApiClient(
        device=ble_device,
        config=conf,
        retry_count=DEFAULT_RETRY_COUNT,
    )
    coordinator = MicroBotDataUpdateCoordinator(
        hass, client=client, ble_device=ble_device
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS
    )

    async def generate_token(call: ServiceCall) -> None:
        _LOGGER.debug("Token service called")
        await coordinator.api.connect(init=True)

    async def calibrate(call: ServiceCall) -> None:
        _LOGGER.debug("Calibrate service called")
        depth = call.data["depth"]
        duration = call.data["duration"]
        mode = call.data["mode"]
        await coordinator.api.connect()
        coordinator.api.setDepth(depth)
        coordinator.api.setDuration(duration)
        coordinator.api.setMode(mode)
        await coordinator.api.calibrate()
        await coordinator.api.disconnect()

    hass.services.async_register(DOMAIN, "generate_token", generate_token)
    hass.services.async_register(DOMAIN, "calibrate", calibrate)
    return True


class MicroBotDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Class to manage fetching data from the MicroBot."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MicroBotApiClient,
        ble_device: BLEDevice,
    ) -> None:
        """Initialize."""
        self.api = client
        self.platforms: list[str] = []
        self._ready_event = asyncio.Event()
        self.data: dict[str, Any] = {}
        self.ble_device = ble_device

        super().__init__(
            hass, _LOGGER, ble_device.address, bluetooth.BluetoothScanningMode.ACTIVE
        )

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        super()._async_handle_bluetooth_event(service_info, change)
        if adv := parse_advertisement_data(
            service_info.device, service_info.advertisement
        ):
            self.data = adv.data
            if self.data:
                self._ready_event.set()
            _LOGGER.debug("%s: MicroBot data: %s", self.ble_device.address, self.data)
            self.api.update_from_advertisement(adv)
        self.async_update_listeners()

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        with contextlib.suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(55):
                await self._ready_event.wait()
                return True
        return False
    
    @property
    def available(self) -> bool:
        """Return true if the switch is available."""
        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded
