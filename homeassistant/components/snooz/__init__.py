"""The Snooz component."""

import logging

from pysnooz import (
    SnoozAdvertisementData,
    SnoozDeviceModel,
    SnoozFirmwareVersion,
    parse_snooz_advertisement,
)
from pysnooz.device import SnoozDevice

from homeassistant.components.bluetooth import (
    BluetoothReachabilityIntent,
    async_address_reachability_diagnostics,
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FIRMWARE_VERSION, DOMAIN, PLATFORMS
from .models import SnoozConfigEntry, SnoozConfigurationData
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Snooz integration."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: SnoozConfigEntry) -> None:
    """Migrate a config entry to the current version."""
    if entry.minor_version < 2:
        # Entries created before minor version 2 only stored the address and
        # pairing token, and the model and firmware version were parsed from
        # the cached advertisement at every setup. Store them once instead.
        address: str = entry.data[CONF_ADDRESS]
        if (service_info := async_last_service_info(hass, address)) is None or (
            advertisement := parse_snooz_advertisement(service_info)
        ) is None:
            raise _async_device_not_found_error(hass, address)

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_MODEL: advertisement.model.value,
                CONF_FIRMWARE_VERSION: advertisement.firmware_version.value,
            },
            minor_version=2,
        )


async def async_setup_entry(hass: HomeAssistant, entry: SnoozConfigEntry) -> None:
    """Set up Snooz device from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    # transitions info logs are verbose. Only enable warnings
    logging.getLogger("transitions.core").setLevel(logging.WARNING)

    if (ble_device := async_ble_device_from_address(hass, address)) is None:
        raise _async_device_not_found_error(hass, address)

    advertisement = SnoozAdvertisementData(
        model=SnoozDeviceModel(entry.data[CONF_MODEL]),
        firmware_version=SnoozFirmwareVersion(entry.data[CONF_FIRMWARE_VERSION]),
        password=entry.data[CONF_TOKEN],
    )
    device = SnoozDevice(ble_device, advertisement)

    entry.runtime_data = SnoozConfigurationData(ble_device, device, entry.title)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


@callback
def _async_device_not_found_error(
    hass: HomeAssistant, address: str
) -> ConfigEntryNotReady:
    """Return the error for a device that is not available over Bluetooth."""
    return ConfigEntryNotReady(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={
            "address": address,
            "reason": async_address_reachability_diagnostics(
                hass,
                address.upper(),
                BluetoothReachabilityIntent.CONNECTION,
            ),
        },
    )


async def _async_update_listener(hass: HomeAssistant, entry: SnoozConfigEntry) -> None:
    """Handle options update."""
    if entry.title != entry.runtime_data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SnoozConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # also called by fan entities, but do it here too for good measure
    await entry.runtime_data.device.async_disconnect()
