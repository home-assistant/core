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
    BluetoothServiceInfo,
    BluetoothScanningMode,
    async_ble_device_from_address,
    async_process_advertisements,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_FIRMWARE_VERSION, DOMAIN, LOGGER, PLATFORMS
from .models import SnoozConfigurationData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snooz device from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    token: str = entry.data[CONF_TOKEN]

    # transitions info logs are verbose. Only enable warnings
    logging.getLogger("transitions.core").setLevel(logging.WARNING)

    if not (ble_device := async_ble_device_from_address(hass, address)):
        raise ConfigEntryNotReady(
            f"Could not find Snooz with address {address}. Try power cycling the device"
        )

    token: str = entry.data[CONF_TOKEN]
    model: int = entry.data[CONF_MODEL]
    firmware_version: int = entry.data[CONF_FIRMWARE_VERSION]
    adv_data = SnoozAdvertisementData(
        SnoozDeviceModel(model), SnoozFirmwareVersion(firmware_version), token
    )
    device = SnoozDevice(ble_device, adv_data)

    device_info = await device.async_get_info()

    if device_info is None:
        await device.async_disconnect()
        raise ConfigEntryError("Failed to get device information")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SnoozConfigurationData(
        ble_device, adv_data, device_info, device, entry.title
    )

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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate configuration entry."""

    # up to date
    if config_entry.version == 2:
        return True

    LOGGER.debug(
        f"Migrating entry {config_entry.entry_id} from version {config_entry.version}"
    )

    address = config_entry.data[CONF_ADDRESS]

    adv_data = await hass.async_create_task(
        async_get_supported_advertisement(hass, address)
    )

    if adv_data is None:
        LOGGER.error(
            f"Could not find supported advertisement for address {address} while migrating entry {config_entry.entry_id}"
        )
        return False

    config_entry.version = 2
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_MODEL: adv_data.model,
            CONF_FIRMWARE_VERSION: adv_data.firmware_version,
        },
    )

    LOGGER.debug(f"Migration complete. Model: {adv_data}")
    return True


async def async_get_supported_advertisement(
    hass: HomeAssistant, address: str
) -> SnoozAdvertisementData | None:
    """Process advertisements for an address until a supported advertisement is found."""

    def is_supported(
        service_info: BluetoothServiceInfo,
    ) -> bool:
        if parse_snooz_advertisement(service_info) is None:
            LOGGER.warning(
                f"Skipped unsupported advertisement: {service_info.name} ({service_info.address})."
            )
            return False

        return True

    try:
        info = await async_process_advertisements(
            hass,
            is_supported,
            {"address": address},
            BluetoothScanningMode.ACTIVE,
            10,
        )

        return parse_snooz_advertisement(info)
    except asyncio.TimeoutError:
        pass

    return None
