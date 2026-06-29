"""Bluetooth proxy for SLZB devices using bleak-smlight."""

from functools import partial

from bleak_smlight import SLZB_BLE_SERVER_PORT, connect_scanner
from pysmlight import BleProxyClient

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import DOMAIN
from .coordinator import SmConfigEntry


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
) -> CALLBACK_TYPE:
    """Connect scanner using the external bleak-smlight backend."""
    assert entry.unique_id is not None

    client_data = connect_scanner(
        source=entry.unique_id,
        name=entry.title,
        host=entry.data[CONF_HOST],
        port=SLZB_BLE_SERVER_PORT,
    )

    client_data.scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)

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
