"""The INKBIRD Bluetooth integration."""

from __future__ import annotations

from typing import Any

from inkbird_ble import INKBIRDBluetoothDeviceData

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_DATA, CONF_DEVICE_TYPE, DOMAIN
from .coordinator import INKBIRDActiveBluetoothProcessorCoordinator

INKBIRDConfigEntry = ConfigEntry[INKBIRDActiveBluetoothProcessorCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: INKBIRDConfigEntry) -> bool:
    """Set up INKBIRD BLE device from a config entry."""
    assert entry.unique_id is not None
    device_type: str | None = entry.data.get(CONF_DEVICE_TYPE)
    device_data: dict[str, Any] | None = entry.data.get(CONF_DEVICE_DATA)
    coordinator = INKBIRDActiveBluetoothProcessorCoordinator(hass, entry)

    @callback
    def _async_device_data_changed(new_device_data: dict[str, Any]) -> None:
        """Handle device data changed."""
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DEVICE_DATA: new_device_data}
        )

    data = INKBIRDBluetoothDeviceData(
        device_type,
        device_data,
        coordinator.async_set_updated_data,
        _async_device_data_changed,
    )
    coordinator.async_set_data(data)
    if data.uses_notify:
        if not (service_info := async_last_service_info(hass, entry.unique_id)):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_advertisement",
                translation_placeholders={"address": entry.unique_id},
            )
        await data.async_start(service_info, service_info.device)
        entry.async_on_unload(data.async_stop)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: INKBIRDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
