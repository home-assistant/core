"""Bluetooth proxy for SLZB devices using bleak-smlight."""

from functools import partial
import logging

from bleak_smlight import SLZB_BLE_SERVER_PORT, connect_scanner
from pysmlight import Api2, BleProxyClient, Info

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_BLE_SCANNER_MODE, DOMAIN, BLEScannerMode
from .coordinator import SmConfigEntry, base_device_info

_LOGGER = logging.getLogger(__name__)


@callback
def _async_unload(
    unload_callbacks: list[CALLBACK_TYPE],
    client: BleProxyClient,
) -> None:
    """Unload callbacks and stop client."""
    for callback_func in unload_callbacks:
        callback_func()
    client.stop()


@callback
def async_connect_scanner(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    model: str | None,
    device_id: str,
    scanner_mode: BluetoothScanningMode = BluetoothScanningMode.AUTO,
) -> CALLBACK_TYPE:
    """Connect scanner using the external bleak-smlight backend."""
    assert entry.unique_id is not None

    client_data = connect_scanner(
        source=entry.unique_id,
        name=entry.title,
        host=entry.data[CONF_HOST],
        port=SLZB_BLE_SERVER_PORT,
    )

    client_data.scanner.async_set_scanning_mode(scanner_mode)

    entry.async_create_background_task(
        hass,
        client_data.client.start(),
        f"smlight-ble-proxy-client-{entry.unique_id}",
    )

    unload_callbacks = [
        async_register_scanner(
            hass,
            client_data.scanner,
            source_domain=DOMAIN,
            source_model=model,
            source_config_entry_id=entry.entry_id,
            source_device_id=device_id,
        ),
        client_data.scanner.async_setup(),
    ]

    return partial(_async_unload, unload_callbacks, client_data.client)


async def async_setup_ble_scanner(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    client: Api2,
    info: Info,
) -> CALLBACK_TYPE | None:
    """Set up the BLE scanner/proxy configuration."""
    assert info.ble is not None

    scanner_mode = get_ble_scanner_mode(entry, info)

    remote_adapter_enabled = scanner_mode != BLEScannerMode.DISABLED

    if remote_adapter_enabled:
        if not info.ble.proxy_enabled:
            _LOGGER.warning(
                "SMLIGHT BLE proxy is enabled in Home Assistant options but disabled on the device. "
                "Please reconfigure the integration options to align settings"
            )
            return None

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **base_device_info(info, client.host),
        )
        return async_connect_scanner(
            hass,
            entry,
            info.model,
            device.id,
            BluetoothScanningMode(scanner_mode),
        )

    return None


@callback
def get_ble_scanner_mode(
    entry: SmConfigEntry,
    info: Info,
) -> BLEScannerMode:
    """Get the BLE scanner mode config or default."""
    if info.ble is None:
        return BLEScannerMode.DISABLED

    return BLEScannerMode(
        entry.options.get(
            CONF_BLE_SCANNER_MODE,
            BLEScannerMode.AUTO if info.ble.proxy_enabled else BLEScannerMode.DISABLED,
        )
    )
