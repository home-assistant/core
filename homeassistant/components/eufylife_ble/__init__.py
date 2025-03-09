"""The EufyLife integration."""

from __future__ import annotations

from eufylife_ble_client import EufyLifeBLEDevice

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.const import CONF_MODEL, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .models import EufyLifeConfigEntry, EufyLifeData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EufyLifeConfigEntry) -> bool:
    """Set up EufyLife device from a config entry."""
    address = entry.unique_id
    assert address is not None

    model = entry.data[CONF_MODEL]
    client = EufyLifeBLEDevice(model=model)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        client.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )
        if not client.advertisement_data_contains_state:
            hass.async_create_task(client.connect())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    entry.runtime_data = EufyLifeData(address, model, client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await client.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EufyLifeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
