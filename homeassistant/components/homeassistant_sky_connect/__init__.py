"""The Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging

from homeassistant.components.homeassistant_hardware.util import guess_firmware_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DESCRIPTION,
    DEVICE,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_VERSION,
    PRODUCT,
    SERIAL_NUMBER,
    HardwareVariant,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""

    variant = HardwareVariant.from_usb_product_name(entry.data[PRODUCT])
    serial_number = entry.data[SERIAL_NUMBER]

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[SERIAL_NUMBER])},
        name="{variant.full_name} ({serial_number[:8]})",
        model=variant.full_name,
        manufacturer="Nabu Casa",
        serial_number=serial_number,
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["update"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating from version %s:%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        if config_entry.minor_version == 1:
            # Add-on startup with type service get started before Core, always (e.g. the
            # Multi-Protocol add-on). Probing the firmware would interfere with the add-on,
            # so we can't safely probe here. Instead, we must make an educated guess!
            firmware_guess = await guess_firmware_info(hass, config_entry.data[DEVICE])

            new_data = {**config_entry.data}
            new_data[FIRMWARE] = firmware_guess.firmware_type.value

            # Copy `description` to `product`
            new_data[PRODUCT] = new_data[DESCRIPTION]

            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                version=1,
                minor_version=2,
            )

        if config_entry.minor_version == 2:
            # Add a `firmware_version` key
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    FIRMWARE_VERSION: None,
                },
                version=1,
                minor_version=3,
            )

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

        return True

    # This means the user has downgraded from a future version
    return False
