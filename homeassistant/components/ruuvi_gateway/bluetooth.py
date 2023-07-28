"""Bluetooth support for Ruuvi Gateway."""
from __future__ import annotations

from collections.abc import Callable
import logging
import time

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .coordinator import RuuviGatewayUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class RuuviGatewayScanner(BaseHaRemoteScanner):
    """Scanner for Ruuvi Gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        name: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        *,
        coordinator: RuuviGatewayUpdateCoordinator,
    ) -> None:
        """Initialize the scanner, using the given update coordinator as data source."""
        super().__init__(
            hass,
            scanner_id,
            name,
            new_info_callback,
            connector=None,
            connectable=False,
        )
        self.coordinator = coordinator

    @callback
    def _async_handle_new_data(self) -> None:
        now = time.time()
        monotonic_now = MONOTONIC_TIME()
        for tag_data in self.coordinator.data:
            data_age_seconds = now - tag_data.timestamp  # Both are Unix time
            if data_age_seconds > FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS:
                # Don't process stale data at all
                continue
            anno = tag_data.parse_announcement()
            self._async_on_advertisement(
                address=tag_data.mac,
                rssi=tag_data.rssi,
                local_name=anno.local_name,
                service_data=anno.service_data,
                service_uuids=anno.service_uuids,
                manufacturer_data=anno.manufacturer_data,
                tx_power=anno.tx_power,
                details={},
                advertisement_monotonic_time=monotonic_now - data_age_seconds,
            )

    @callback
    def start_polling(self) -> CALLBACK_TYPE:
        """Start polling; return a callback to stop polling."""
        return self.coordinator.async_add_listener(self._async_handle_new_data)


def async_connect_scanner(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: RuuviGatewayUpdateCoordinator,
) -> tuple[RuuviGatewayScanner, CALLBACK_TYPE]:
    """Connect scanner and start polling."""
    assert entry.unique_id is not None
    source = str(entry.unique_id)
    _LOGGER.debug(
        "%s [%s]: Connecting scanner",
        entry.title,
        source,
    )
    scanner = RuuviGatewayScanner(
        hass=hass,
        scanner_id=source,
        name=entry.title,
        new_info_callback=async_get_advertisement_callback(hass),
        coordinator=coordinator,
    )
    unload_callbacks = [
        async_register_scanner(hass, scanner, connectable=False),
        scanner.async_setup(),
        scanner.start_polling(),
    ]

    @callback
    def _async_unload() -> None:
        for unloader in unload_callbacks:
            unloader()

    return (scanner, _async_unload)
