"""BLE proxy client for the Matter integration.

Thin Home Assistant adapter around the `matter_ble_proxy` library: the protocol
logic, command dispatch, binary frame handling, and connection bookkeeping live
in the library; this module only provides HA-specific `BleScanSource` and
`BleDeviceResolver` backends that wire into Home Assistant's bluetooth
component (which transparently supports ESPHome BLE proxies).

See `docs/ble-proxy-protocol.md` in the matter-server repository for the
protocol specification.
"""

from collections.abc import Callable
import logging

from bleak.backends.device import BLEDevice
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from matter_ble_proxy import (
    AdvertisementData,
    BleDeviceResolver,
    BleScanSource,
    MatterBleProxy,
)

from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BluetoothScanningMode,
    async_ble_device_from_address,
    async_register_callback,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


class HaBluetoothScanSource(BleScanSource):
    """`BleScanSource` backed by Home Assistant's bluetooth component.

    HA owns the BLE adapter; we only register an advertisement callback so the
    adapter is never started/stopped from here.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._cancel: CALLBACK_TYPE | None = None

    async def start(  # pylint: disable=arguments-renamed
        self, callback_fn: Callable[[AdvertisementData], None]
    ) -> None:
        """Register an advertisement callback with HA's bluetooth component."""
        if self._cancel is not None:
            return

        # Drop HA's synchronous replay of stale history on register; otherwise a
        # rotating peripheral's old addresses each become a parallel connect candidate.
        # `MONOTONIC_TIME` is the clock that stamps `service_info.time`.
        scan_start = MONOTONIC_TIME()

        @callback
        def _on_advertisement(
            service_info: BluetoothServiceInfoBleak,
            _change: object,
        ) -> None:
            if service_info.time < scan_start:
                return
            try:
                callback_fn(_to_advertisement_data(service_info))
            except Exception:
                _LOGGER.exception("BLE proxy advertisement forward failed")

        self._cancel = async_register_callback(
            self._hass,
            _on_advertisement,
            None,
            BluetoothScanningMode.PASSIVE,
        )

    async def stop(self) -> None:
        """Unregister the advertisement callback."""
        if self._cancel is not None:
            self._cancel()
            self._cancel = None


class HaBluetoothDeviceResolver(BleDeviceResolver):
    """`BleDeviceResolver` that asks HA's bluetooth registry for a `BLEDevice`."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass

    async def resolve(self, address: str) -> BLEDevice | None:
        """Return HA's cached BLEDevice for `address`, or None if unknown."""
        return async_ble_device_from_address(self._hass, address, connectable=True)


def _to_advertisement_data(
    service_info: BluetoothServiceInfoBleak,
) -> AdvertisementData:
    """Translate HA's `BluetoothServiceInfoBleak` to the library's wire type."""
    return AdvertisementData(
        address=service_info.address,
        name=service_info.name,
        rssi=service_info.rssi,
        connectable=service_info.connectable,
        service_data=dict(service_info.service_data),
        manufacturer_data=dict(service_info.manufacturer_data),
        service_uuids=list(service_info.service_uuids),
    )


def create_matter_ble_proxy(hass: HomeAssistant, ws_url: str) -> MatterBleProxy:
    """Return a `MatterBleProxy` wired into Home Assistant's bluetooth component."""
    return MatterBleProxy(
        ws_url=ws_url,
        scan_source=HaBluetoothScanSource(hass),
        device_resolver=HaBluetoothDeviceResolver(hass),
        task_factory=lambda coro: hass.async_create_background_task(
            coro, name="matter_ble_proxy"
        ),
    )
