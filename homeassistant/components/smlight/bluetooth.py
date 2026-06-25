"""Bluetooth proxy for SLZB devices."""

import logging
from typing import override

from pysmlight import BleProxyClient

from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import DOMAIN
from .coordinator import SmConfigEntry

_LOGGER = logging.getLogger(__name__)


class SmBleScanner(BaseHaRemoteScanner):
    """Bluetooth scanner for SLZB devices."""

    __slots__ = (
        "_client",
        "esp32_ip",
        "esp32_port",
        "hass",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        name: str,
        esp32_ip: str,
        esp32_port: int,
    ) -> None:
        """Initialize the SLZB Bluetooth scanner."""
        super().__init__(
            source=scanner_id,
            adapter=name,
            connector=None,
            connectable=False,
            requested_mode=BluetoothScanningMode.ACTIVE,
            current_mode=BluetoothScanningMode.ACTIVE,
        )
        self.hass = hass
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self._client: BleProxyClient | None = None

    @callback
    def _handle_raw_advertisement(
        self,
        device_mac: str,
        rssi: int,
        address_type: int,
        raw_data: bytes,
    ) -> None:
        self._async_on_raw_advertisement(
            address=device_mac,
            rssi=rssi,
            raw=raw_data,
            details={"address_type": address_type},
            advertisement_monotonic_time=MONOTONIC_TIME(),
        )

    async def _async_start_client(self) -> None:
        """Start the BLE proxy client."""
        if self._client is None:
            return
        await self._client.start()

    @override
    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the SLZB Bluetooth scanner."""
        cancel_watchdog = super().async_setup()
        self._client = BleProxyClient(
            esp32_ip=self.esp32_ip,
            callback=self._handle_raw_advertisement,
            esp32_port=self.esp32_port,
        )
        self.hass.async_create_background_task(
            self._async_start_client(), f"smlight-ble-proxy-client-{self.source}"
        )

        @callback
        def _async_unload() -> None:
            cancel_watchdog()

            if self._client:
                self._client.stop()
                self._client = None

        return _async_unload


@callback
def async_connect_scanner(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    model: str | None,
    device_id: str,
) -> CALLBACK_TYPE:
    """Connect scanner and return unsetup callback."""
    assert entry.unique_id is not None
    scanner = SmBleScanner(
        hass=hass,
        scanner_id=entry.unique_id,
        name=entry.title,
        esp32_ip=entry.data[CONF_HOST],
        esp32_port=5050,
    )
    unload_callbacks = [
        async_register_scanner(
            hass,
            scanner,
            source_domain=DOMAIN,
            source_model=model,
            source_config_entry_id=entry.entry_id,
            source_device_id=device_id,
        ),
        scanner.async_setup(),
    ]

    @callback
    def _async_unload() -> None:
        for callback_func in unload_callbacks:
            callback_func()

    return _async_unload
