"""The chacon_dio integration."""

from dataclasses import dataclass
import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH]

SERVICE_RELOAD_STATE = "reload_state"


@dataclass
class ChaconDioData:
    """Chacon Dio data class."""

    client: DIOChaconAPIClient
    list_devices: list[dict[str, Any]]


type ChaconDioConfigEntry = ConfigEntry[ChaconDioData]


async def async_setup_entry(hass: HomeAssistant, entry: ChaconDioConfigEntry) -> bool:
    """Set up chacon_dio from a config entry."""

    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    dio_chacon_id = entry.unique_id

    _LOGGER.debug("Initializing Chacon Dio client %s, %s", username, dio_chacon_id)
    client = DIOChaconAPIClient(
        username,
        password,
        dio_chacon_id,
    )

    found_devices = await client.search_all_devices(with_state=True)
    list_devices = list(found_devices.values())
    _LOGGER.debug("List of devices %s", list_devices)

    entry.runtime_data = ChaconDioData(
        client=client,
        list_devices=list_devices,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def reload_devices_states(call: ServiceCall) -> None:
        """Trigger a reload of the states of the devices."""
        # No data input to call the service

        _LOGGER.debug("Call to the reload service for all dio chacon devices")
        registry = er.async_get(hass)

        entries = registry.entities.get_entries_for_config_entry_id(entry.entry_id)

        if entries:
            ids: list = [d.unique_id for d in entries]
            # Get the details of all the devices from the server
            # The update information is sent via callback to the effective entity
            await client.get_status_details(ids, True)

    # This service allows user to reload all devices data from the server.
    hass.services.async_register(DOMAIN, SERVICE_RELOAD_STATE, reload_devices_states)

    # Disconnect the permanent websocket connection of home assistant on shutdown
    async def _async_disconnect_websocket(_: Event) -> None:
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hass.services.async_remove(DOMAIN, SERVICE_RELOAD_STATE)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.disconnect()

    return unload_ok
