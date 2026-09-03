"""Polling, and what to do when the sensor stops answering."""

from datetime import timedelta
import logging
from typing import override

from ecowitt_modbus import EcowittDevice, NotThisDeviceError
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type EcowittConfigEntry = ConfigEntry[EcowittDataUpdateCoordinator]


class EcowittDataUpdateCoordinator(DataUpdateCoordinator[EcowittDevice]):
    """Poll one sensor array's live weather readings."""

    config_entry: EcowittConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EcowittConfigEntry,
        device: EcowittDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    @cached_property
    def identity(self) -> str:
        """What this entry's device and entities are keyed on.

        A model that reports a serial number is keyed on it, so the device
        survives being moved to another address. A model that reports none
        falls back to the config entry itself -- an address would go stale
        the moment the device moved, taking every entity's history with it.
        """
        entry = self.config_entry
        return entry.unique_id or entry.entry_id

    @cached_property
    def device_info(self) -> DeviceInfo:
        """The one sensor array every entity on this config entry belongs to.

        ``name`` has to be passed explicitly rather than left to the device
        registry's own config-entry-title fallback: that fallback only
        applies the first time the device is created, so on reconfigure
        (an update to an existing device, not a new one) an omitted name
        would leave the device and its entities showing the old address.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.identity)},
            name=self.config_entry.title,
            manufacturer=self.device.manufacturer,
            model=self.device.MODEL,
            serial_number=self.device.serial_number,
            sw_version=self.device.sw_version,
        )

    def _check_serial_number(self) -> None:
        """Fail if a device that reports an identity reports the wrong one.

        The address in ``entry.data`` can come to point at a different
        responder than the entry was created for -- the gateway is
        reconfigured, a device address is reused. A model that reports a
        serial number (the WN90LP) refreshes it on every poll, so a swap is
        caught whenever it happens rather than only at setup.

        A model that reports no serial number (the WN69LP) has nothing to
        check: its entry is tied to an address, and a different device at
        that address is indistinguishable. That limitation is documented
        rather than papered over.
        """
        serial = self.device.serial_number
        if serial is not None and serial != self.config_entry.unique_id:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="wrong_serial_number",
                translation_placeholders={
                    "expected": self.config_entry.unique_id or "unknown",
                    "found": serial,
                },
            )

    @override
    async def _async_setup(self) -> None:
        """Confirm the expected model answers before creating any entities.

        Runs once per setup, ahead of the first refresh, so an entry pointed
        at the wrong device never reaches the point of registering entities
        for it.
        """
        try:
            await self.device.async_probe()
        except ModbusError as err:
            # Not answering yet is worth retrying; the wrong device is not.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except NotThisDeviceError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unexpected_device",
                translation_placeholders={
                    "model": self.device.MODEL,
                    "error": str(err),
                },
            ) from err

        self._check_serial_number()

    @override
    async def _async_update_data(self) -> EcowittDevice:
        try:
            await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        self._check_serial_number()
        return self.device
