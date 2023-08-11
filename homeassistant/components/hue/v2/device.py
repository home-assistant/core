"""Handles Hue resource of type `device` mapping to Home Assistant device."""
from typing import TYPE_CHECKING

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.device import Device, DeviceArchetypes

from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_SW_VERSION,
    ATTR_VIA_DEVICE,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr

from ..const import DOMAIN

if TYPE_CHECKING:
    from ..bridge import HueBridge


async def async_setup_devices(bridge: "HueBridge"):
    """Manage setup of devices from Hue devices."""
    entry = bridge.config_entry
    hass = bridge.hass
    api: HueBridgeV2 = bridge.api  # to satisfy typing
    dev_reg = dr.async_get(hass)
    dev_controller = api.devices

    @callback
    def add_device(hue_device: Device) -> dr.DeviceEntry:
        """Register a Hue device in device registry."""
        model = f"{hue_device.product_data.product_name} ({hue_device.product_data.model_id})"
        params = {
            ATTR_IDENTIFIERS: {(DOMAIN, hue_device.id)},
            ATTR_SW_VERSION: hue_device.product_data.software_version,
            ATTR_NAME: hue_device.metadata.name,
            ATTR_MODEL: model,
            ATTR_MANUFACTURER: hue_device.product_data.manufacturer_name,
        }
        if room := dev_controller.get_room(hue_device.id):
            params[ATTR_SUGGESTED_AREA] = room.metadata.name
        if hue_device.metadata.archetype == DeviceArchetypes.BRIDGE_V2:
            params[ATTR_IDENTIFIERS].add((DOMAIN, api.config.bridge_id))
        else:
            params[ATTR_VIA_DEVICE] = (DOMAIN, api.config.bridge_device.id)
        zigbee = dev_controller.get_zigbee_connectivity(hue_device.id)
        if zigbee and zigbee.mac_address:
            params[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, zigbee.mac_address)}

        return dev_reg.async_get_or_create(config_entry_id=entry.entry_id, **params)

    @callback
    def remove_device(hue_device_id: str) -> None:
        """Remove device from registry."""
        if device := dev_reg.async_get_device(identifiers={(DOMAIN, hue_device_id)}):
            # note: removal of any underlying entities is handled by core
            dev_reg.async_remove_device(device.id)

    @callback
    def handle_device_event(evt_type: EventType, hue_device: Device) -> None:
        """Handle event from Hue devices controller."""
        if evt_type == EventType.RESOURCE_DELETED:
            remove_device(hue_device.id)
        else:
            # updates to existing device will also be handled by this call
            add_device(hue_device)

    # create/update all current devices found in controller
    known_devices = [add_device(hue_device) for hue_device in dev_controller]

    # Check for nodes that no longer exist and remove them
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if device not in known_devices:
            # handle case where a virtual device was created for a Hue group
            hue_dev_id = next(x[1] for x in device.identifiers if x[0] == DOMAIN)
            if hue_dev_id in api.groups:
                continue
            dev_reg.async_remove_device(device.id)

    # add listener for updates on Hue devices controller
    entry.async_on_unload(dev_controller.subscribe(handle_device_event))
