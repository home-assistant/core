"""The TIS Control integration."""

from __future__ import annotations

import logging

from attr import dataclass
from TISApi.api import TISApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEVICES_DICT, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TISData:
    """TIS Control data stored in the ConfigEntry."""

    tis_api: TISApi


# Define the Home Assistant platforms that this integration will support.
PLATFORMS: list[Platform] = [Platform.SWITCH]

# Create a type alias for a ConfigEntry specific to this integration.
type TISConfigEntry = ConfigEntry[TISData]


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Set up TIS Control from a config entry."""
    # Get the TISApi instance from the user's entry.
    tis_api: TISApi = TISApi(
        port=int(entry.data[CONF_PORT]),
        domain=DOMAIN,
        devices_dict=DEVICES_DICT,
    )

    try:
        await tis_api.connect()
    except ConnectionError as e:
        # If connection fails, raise ConfigEntryNotReady
        # to prompt Home Assistant to retry setup later.
        _LOGGER.error("Failed to connect: %s", e)
        raise ConfigEntryNotReady(
            f"Failed to connect to TIS API Gateway, error: {e}"
        ) from e

    entry.runtime_data = TISData(tis_api=tis_api)

    async def listen_for_events():
        # This will run forever, pulling data from the library
        async for event in tis_api.consume_events():
            device_id = event["device_id"]
            hass.bus.async_fire(f"tis_device_{device_id}", event)

    # Add this listener to the HA loop as a background task
    entry.async_create_background_task(hass, listen_for_events(), "tis_event_listener")

    try:
        await tis_api.scan_devices()
    except ConnectionError as e:
        _LOGGER.error(
            "Connection Error happened while scanning the network for devices: %s",
            str(e),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the platforms associated with this entry, which will remove the entities.
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return unload_ok

    return False
