"""The Snooz component."""
from __future__ import annotations

import asyncio
import logging

from pysnooz import (
    SnoozAdvertisementData,
    SnoozDeviceModel,
    SnoozFirmwareVersion,
    parse_snooz_advertisement,
)
from pysnooz.device import SnoozDevice

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_ble_device_from_address,
    async_process_advertisements,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_FIRMWARE_VERSION, DOMAIN, LOGGER, PLATFORMS
from .models import SnoozConfigurationData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snooz device from a config entry."""
    # transitions info logs are verbose. Only enable warnings
    logging.getLogger("transitions.core").setLevel(logging.WARNING)

    config_data = await _async_load_entry_data(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = config_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: SnoozConfigurationData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: SnoozConfigurationData = hass.data[DOMAIN][entry.entry_id]

        # also called by fan entities, but do it here too for good measure
        await data.device.async_disconnect()

        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok


async def _async_load_entry_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> SnoozConfigurationData:
    if _entry_missing_device_config(entry):
        adv_data = await _async_update_entry_config(hass, entry)
    else:
        adv_data = _load_entry_config(entry)

    address: str = entry.data[CONF_ADDRESS]
    if not (ble_device := async_ble_device_from_address(hass, address)):
        raise ConfigEntryNotReady(
            f"Could not find Snooz with address {address}. Try power cycling the device"
        )

    return SnoozConfigurationData(
        ble_device,
        adv_data,
        device=SnoozDevice(ble_device, adv_data),
        title=entry.title,
    )


def _entry_missing_device_config(entry: ConfigEntry) -> bool:
    return CONF_MODEL not in entry.data or CONF_FIRMWARE_VERSION not in entry.data


def _load_entry_config(entry: ConfigEntry) -> SnoozAdvertisementData:
    return SnoozAdvertisementData(
        model=SnoozDeviceModel(entry.data[CONF_MODEL]),
        firmware_version=SnoozFirmwareVersion(entry.data[CONF_FIRMWARE_VERSION]),
        password=entry.data[CONF_TOKEN],
    )


async def _async_update_entry_config(
    hass: HomeAssistant, entry: ConfigEntry
) -> SnoozAdvertisementData:
    """Find a supported advertisement and store data in config entry."""

    address = entry.data[CONF_ADDRESS]
    LOGGER.debug(f"Loading device information from advertisement for address {address}")

    adv_data = await hass.async_create_task(
        _async_wait_for_advertisement(hass, address)
    )

    if adv_data is None:
        raise ConfigEntryNotReady(
            f"Could not find supported advertisement for address {address}."
            " Try power cycling the device"
        )

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_MODEL: adv_data.model,
            CONF_FIRMWARE_VERSION: adv_data.firmware_version,
        },
    )

    # use token from config entry since we don't require
    # pairing mode to load the data from an advertisement
    adv_data.password = entry.data[CONF_TOKEN]

    return adv_data


async def _async_wait_for_advertisement(
    hass: HomeAssistant, address: str
) -> SnoozAdvertisementData | None:
    """Process advertisements for an address until a supported advertisement is found."""

    def is_supported_advertisement(
        service_info: BluetoothServiceInfo,
    ) -> bool:
        if parse_snooz_advertisement(service_info) is None:
            LOGGER.warning(
                f"Skipping unsupported advertisement with name: {service_info.name}"
            )
            return False

        return True

    try:
        supported_info = await async_process_advertisements(
            hass,
            is_supported_advertisement,
            {"address": address},
            BluetoothScanningMode.ACTIVE,
            10,
        )

        return parse_snooz_advertisement(supported_info)
    except asyncio.TimeoutError:
        pass

    return None
