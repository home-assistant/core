"""services for yolink integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .const import DOMAIN
from .device_impl import YoLinkOutlet, YoLinkSiren

__Logger = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up services for the yolink component."""

    async def change_siren_state(device_id, yl_device_id, state):
        """Change siren state."""
        __Logger.info("call Siren State Change api")
        registry = await entity_registry.async_get_registry(hass)
        device_siren_entity = entity_registry.async_entries_for_device(
            registry, device_id
        )[0]
        for device in hass.data[DOMAIN][config_entry.entry_id]["devices"]:
            if yl_device_id == device["deviceId"]:
                siren_device = YoLinkSiren(device, hass, config_entry)
                siren_device.siren_entiry.hass = hass
                siren_device.siren_entiry.entity_id = device_siren_entity.entity_id
                await siren_device.siren_entiry.async_turn_on_off(state)

    async def change_outlet_state(device_id, yl_device_id, state):
        """Change outlet state."""
        __Logger.info("outlet change state.")
        registry = await entity_registry.async_get_registry(hass)
        device_outlet_entity = entity_registry.async_entries_for_device(
            registry, device_id
        )[0]
        for device in hass.data[DOMAIN][config_entry.entry_id]["devices"]:
            if yl_device_id == device["deviceId"]:
                outlet_device = YoLinkOutlet(device, hass, config_entry)
                outlet_device.light_entity.hass = hass
                outlet_device.light_entity.entity_id = device_outlet_entity.entity_id
                await outlet_device.async_turn_on_off(state)

    async def siren_turn_on(service_call):
        """Service call for siren turn on."""
        __Logger.info("call siren turn on service...")
        device_id = service_call.data["device_id"]
        yl_device_id = service_call.data["yl_device_id"]
        hass.create_task(change_siren_state(device_id, yl_device_id, True))

    async def siren_turn_off(service_call):
        """Service call for siren turn off."""
        device_id = service_call.data["device_id"]
        yl_device_id = service_call.data["yl_device_id"]
        hass.create_task(change_siren_state(device_id, yl_device_id, False))

    async def outlet_turn_on(service_call):
        """Service call for outlet turn on."""
        device_id = service_call.data["device_id"]
        yl_device_id = service_call.data["yl_device_id"]
        hass.create_task(change_outlet_state(device_id, yl_device_id, True))

    async def outlet_turn_off(service_call):
        """Service call for outlet turn off."""
        device_id = service_call.data["device_id"]
        yl_device_id = service_call.data["yl_device_id"]
        hass.create_task(change_outlet_state(device_id, yl_device_id, False))

    hass.services.async_register(DOMAIN, "siren_turn_on", siren_turn_on)
    hass.services.async_register(DOMAIN, "siren_turn_off", siren_turn_off)
    hass.services.async_register(DOMAIN, "outlet_turn_on", outlet_turn_on)
    hass.services.async_register(DOMAIN, "outlet_turn_off", outlet_turn_off)
