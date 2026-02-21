"""Home Assistant coordinator for BLE Battery Management System integration."""

from collections import deque
from datetime import timedelta
from time import monotonic
from typing import Final

from aiobmsble import BMSSample
from aiobmsble.basebms import BaseBMS
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_last_service_info,
)
from homeassistant.components.bluetooth.const import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, LOW_RSSI, UPDATE_INTERVAL


class BTBmsCoordinator(DataUpdateCoordinator[BMSSample]):
    """Update coordinator for a battery management system."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: BLEDevice,
        bms_device: BaseBMS,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize BMS data coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=config_entry.title,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,  # only update when sensor value has changed
            config_entry=config_entry,
        )
        self._device: Final = bms_device
        self._link_q: deque[bool] = deque(
            [False], maxlen=100
        )  # track BMS update issues
        self._mac: Final = ble_device.address
        self._stale: bool = False  # indicates no BMS response for significant time

        LOGGER.debug(
            "Initializing coordinator for %s (%s) as %s",
            self.name,
            self._mac,
            bms_device.bms_id(),
        )

        if service_info := async_last_service_info(
            self.hass, address=self._mac, connectable=True
        ):
            LOGGER.debug("%s: advertisement: %s", self.name, service_info.as_dict())

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac), (BLUETOOTH_DOMAIN, self._mac)},
            connections={(CONNECTION_BLUETOOTH, self._mac)},
        )

    @property
    def rssi(self) -> int | None:
        """Return RSSI value for target BMS."""

        service_info: BluetoothServiceInfoBleak | None = async_last_service_info(
            self.hass, address=self._mac, connectable=True
        )
        return service_info.rssi if service_info else None

    @property
    def link_quality(self) -> int:
        """Gives the percentage of successful BMS reads out of the last 100 attempts."""

        return self._link_q.count(True) * 100 // len(self._link_q)

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        LOGGER.debug("Shutting down BMS (%s)", self.name)
        await super().async_shutdown()
        await self._device.disconnect()

    def _device_stale(self) -> bool:
        if self._link_q[-1]:
            self._stale = False
        elif (
            not self._stale
            and self.link_quality <= 10
            and list(self._link_q)[-10:] == [False] * 10
        ):
            rssi: Final = self.rssi
            LOGGER.error(
                "%s: BMS is stale, triggering reconnect%s!",
                self.name,
                f", check signal strength ({rssi} dBm)"
                if rssi is not None and rssi < LOW_RSSI
                else "",
            )
            self._stale = True

        return self._stale

    async def _async_setup(self) -> None:
        bms_info: Final = await self._device.device_info()
        self.device_info.update(
            DeviceInfo(
                name=bms_info.get("name") or self.name,
                manufacturer=bms_info.get("manufacturer")
                or self._device.INFO.get("default_manufacturer"),
                model=bms_info.get("model") or self._device.INFO.get("default_model"),
                sw_version=bms_info.get("sw_version") or bms_info.get("fw_version"),
                hw_version=bms_info.get("hw_version"),
                model_id=bms_info.get("model_id"),
                serial_number=bms_info.get("serial_number"),
            )
        )

    async def _async_update_data(self) -> BMSSample:
        """Return the latest data from the device."""

        LOGGER.debug("%s: BMS data update", self.name)

        if self._device_stale():
            await self._device.disconnect(reset=True)

        start: Final = monotonic()
        try:
            if not (bms_data := await self._device.async_update()):
                raise UpdateFailed("no valid data received.")
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="bms_timeout"
            ) from err
        except (BleakError, EOFError) as err:
            rssi: Final = self.rssi
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="bms_com_fail_rssi"
                if not rssi or rssi < LOW_RSSI
                else "bms_com_fail",
                translation_placeholders={
                    "rssi": f"{rssi}" if rssi is not None else "--",
                    "err_msg": f"{err!s} ({type(err).__name__})",
                },
            ) from err
        finally:
            self._link_q.extend(
                [False] * (1 + int((monotonic() - start) / UPDATE_INTERVAL))
            )

        self._link_q[-1] = True  # set success
        LOGGER.debug("%s: BMS data sample %s", self.name, bms_data)

        return bms_data
