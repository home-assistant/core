"""The Enphase Envoy integration."""

from __future__ import annotations

from pyenphase import Envoy

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: EnphaseConfigEntry) -> bool:
    """Set up Enphase Envoy from a config entry."""

    host = entry.data[CONF_HOST]
    envoy = Envoy(host, get_async_client(hass, verify_ssl=False))
    coordinator = EnphaseUpdateCoordinator(hass, envoy, entry)

    await coordinator.async_config_entry_first_refresh()
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=envoy.serial_number)

    if entry.unique_id != envoy.serial_number:
        # If the serial number of the device does not match the unique_id
        # of the config entry, it likely means the DHCP lease has expired
        # and the device has been assigned a new IP address. We need to
        # wait for the next discovery to find the device at its new address
        # and update the config entry so we do not mix up devices.
        raise ConfigEntryNotReady(
            f"Unexpected device found at {host}; expected {entry.unique_id}, "
            f"found {envoy.serial_number}"
        )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnphaseConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: EnphaseUpdateCoordinator = entry.runtime_data
    coordinator.async_cancel_token_refresh()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: EnphaseConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove an enphase_envoy config entry from a device."""
    dev_ids = {dev_id[1] for dev_id in device_entry.identifiers if dev_id[0] == DOMAIN}
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    envoy_serial_num = config_entry.unique_id
    if envoy_serial_num in dev_ids:
        return False
    if envoy_data and envoy_data.inverters:
        for inverter in envoy_data.inverters:
            if str(inverter) in dev_ids:
                return False
    return True
