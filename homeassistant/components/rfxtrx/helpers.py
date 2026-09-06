"""Provides helpers for RFXtrx."""

from RFXtrx import RFXtrxDevice, get_device

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from . import (
    get_device_tuple_from_device,
    get_rfx_object,
    get_subentry_id_from_identifiers,
)
from .const import CONF_DATA_BITS, CONF_EVENT_CODE


@callback
def async_get_device_object(hass: HomeAssistant, device_id: str) -> RFXtrxDevice:
    """Get a device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if registry_device is None:
        raise ValueError(f"Device {device_id} not found")

    subentry_id = get_subentry_id_from_identifiers(registry_device.identifiers)
    if subentry_id is None:
        raise ValueError(f"Device {device_id} has no rfxtrx identifier")
    entry = hass.config_entries.async_get_entry(registry_device.primary_config_entry)
    assert entry
    subentry = entry.subentries[subentry_id]

    event = get_rfx_object(subentry.data[CONF_EVENT_CODE])
    if event is None:
        raise ValueError(f"Device {device_id} has an invalid event code")
    device_tuple = get_device_tuple_from_device(
        event.device, data_bits=subentry.data.get(CONF_DATA_BITS)
    )

    return get_device(
        int(device_tuple.packettype, 16),
        int(device_tuple.subtype, 16),
        device_tuple.id_string,
    )
