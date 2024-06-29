"""The dio_chacon integration."""

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
from homeassistant.core import Event, HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


@dataclass
class DioChaconData:
    """Dio Chacon data class."""

    dio_chacon_client: DIOChaconAPIClient
    list_devices: list[dict[str, Any]]


type DioChaconConfigEntry = ConfigEntry[DioChaconData]


async def async_setup_entry(hass: HomeAssistant, entry: DioChaconConfigEntry) -> bool:
    """Set up dio_chacon from a config entry."""

    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    dio_chacon_id = entry.unique_id

    _LOGGER.debug("Initializing Dio Chacon client %s, %s", username, dio_chacon_id)
    dio_chacon_client: DIOChaconAPIClient = DIOChaconAPIClient(
        username,
        password,
        dio_chacon_id,
    )

    found_devices = await dio_chacon_client.search_all_devices(with_state=True)
    list_devices = found_devices.values()
    _LOGGER.debug("List of devices %s", list_devices)

    entry.runtime_data = DioChaconData(
        dio_chacon_client=dio_chacon_client,
        list_devices=list_devices,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Disconnect the permanent websocket connection of home assistant on shutdown
    async def _async_disconnect_websocket(_: Event) -> None:
        await dio_chacon_client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.dio_chacon_client.disconnect()

    return unload_ok
