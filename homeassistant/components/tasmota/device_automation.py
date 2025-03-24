"""Provides device automations for Tasmota."""

from __future__ import annotations

from hatasmota.const import AUTOMATION_TYPE_TRIGGER
from hatasmota.models import DiscoveryHashType
from hatasmota.trigger import TasmotaTrigger

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import device_trigger
from .const import DATA_REMOVE_DISCOVER_COMPONENT, DATA_UNSUB
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW


async def async_remove_automations(hass: HomeAssistant, device_id: str) -> None:
    """Remove automations for a Tasmota device."""
    await device_trigger.async_remove_triggers(hass, device_id)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up Tasmota device automation dynamically through discovery."""

    async def async_device_removed(
        event: Event[EventDeviceRegistryUpdatedData],
    ) -> None:
        """Handle the removal of a device."""
        await async_remove_automations(hass, event.data["device_id"])

    @callback
    def _async_device_removed_filter(
        event_data: EventDeviceRegistryUpdatedData,
    ) -> bool:
        """Filter device registry events."""
        return event_data["action"] == "remove"

    async def async_discover(
        tasmota_automation: TasmotaTrigger, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota device automation."""
        if tasmota_automation.automation_type == AUTOMATION_TYPE_TRIGGER:
            await device_trigger.async_setup_trigger(
                hass, tasmota_automation, config_entry, discovery_hash
            )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format("device_automation")] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format("device_automation"),
            async_discover,
        )
    )
    hass.data[DATA_UNSUB].append(
        hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED,
            async_device_removed,
            event_filter=_async_device_removed_filter,
        )
    )
