"""Platform for sensor integration."""
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .entity_classes import (
    DevoloNetworkOverviewEntity,
    DevoloWifiClientsEntity,
    DevoloWifiNetworksEntity,
)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device = hass.data[DOMAIN][entry.entry_id]["device"]
    plc_entities = [DevoloNetworkOverviewEntity]
    wifi_entities = [DevoloWifiClientsEntity, DevoloWifiNetworksEntity]

    entities = []
    for entity in plc_entities:
        entities.append(entity(device, entry.title))
    if "wifi1" in device.device.features:
        for entity in wifi_entities:
            entities.append(entity(device, entry.title))
    async_add_entities(entities)
