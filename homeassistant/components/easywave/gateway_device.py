"""Device registry helpers for the Easywave RX11 gateway."""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    DOMAIN,
    UNKNOWN_USB_SERIAL,
    normalized_usb_serial,
)
from .transceiver import RX11Transceiver

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import EasywaveConfigEntry


def _connected_serial(transceiver: RX11Transceiver) -> str | None:
    """Return the connected stick's serial, ignoring the unknown placeholder."""
    serial = transceiver.usb_serial_number
    if not isinstance(serial, str):
        return None
    return normalized_usb_serial(serial)


def _remember_connected_stick(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    transceiver: RX11Transceiver,
    serial_number: str | None,
) -> None:
    """Store a replacement RX11's serial and path on the config entry."""
    stored_serial = normalized_usb_serial(entry.data.get(CONF_USB_SERIAL_NUMBER))
    stored_path = entry.data.get(CONF_DEVICE_PATH)
    path = getattr(transceiver, "device_path", None)
    if not isinstance(path, str):
        path = None
    # A missing reading must not wipe a known serial; lookup can fail on a proxy.
    if serial_number is None:
        serial_number = stored_serial

    data_updates: dict[str, Any] = {}
    if serial_number != stored_serial and serial_number is not None:
        data_updates[CONF_USB_SERIAL_NUMBER] = serial_number
    if path and path != stored_path:
        data_updates[CONF_DEVICE_PATH] = path

    if data_updates:
        unique_id = entry.unique_id
        if CONF_USB_SERIAL_NUMBER in data_updates:
            unique_id = f"easywave_{serial_number}"
            conflict = hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            if conflict is not None and conflict.entry_id != entry.entry_id:
                unique_id = entry.unique_id
        if stored_serial != serial_number:
            _LOGGER.info(
                "RX11 %s replaced by %s on %s",
                stored_serial or UNKNOWN_USB_SERIAL,
                serial_number,
                path or stored_path,
            )
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, **data_updates},
            unique_id=unique_id,
        )

    adopt = getattr(transceiver, "adopt_connected_identity", None)
    if adopt is not None:
        adopt()


def update_gateway_device(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    transceiver: RX11Transceiver,
) -> None:
    """Create or update the RX11 gateway device in the device registry."""
    # Always derive serial from the connected stick so a replacement without a
    # readable serial clears any previously stored device-registry value.
    serial_number = _connected_serial(transceiver)
    _remember_connected_stick(hass, entry, transceiver, serial_number)

    hw_version = transceiver.hw_version
    if not isinstance(hw_version, str):
        hw_version = None

    sw_version = transceiver.fw_version
    if not isinstance(sw_version, str):
        sw_version = None

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_USB_PRODUCT) or "RX11 USB Transceiver",
        manufacturer=entry.data.get(CONF_USB_MANUFACTURER) or "ELDAT",
        model=entry.data.get(CONF_USB_PRODUCT) or "RX11 USB Transceiver",
        hw_version=hw_version,
        sw_version=sw_version,
        serial_number=serial_number,
    )
