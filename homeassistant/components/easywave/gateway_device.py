"""Device registry helpers for the Easywave RX11 gateway."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_USB_MANUFACTURER,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    DOMAIN,
)
from .transceiver import RX11Transceiver

if TYPE_CHECKING:
    from . import EasywaveConfigEntry


def update_gateway_device(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    transceiver: RX11Transceiver,
) -> None:
    """Create or update the RX11 gateway device in the device registry."""
    serial_number = transceiver.usb_serial_number
    if not isinstance(serial_number, str):
        serial_number = entry.data.get(CONF_USB_SERIAL_NUMBER)

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
        serial_number=serial_number,
        hw_version=hw_version,
        sw_version=sw_version,
    )
