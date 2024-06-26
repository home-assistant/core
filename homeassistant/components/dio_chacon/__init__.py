"""The dio_chacon integration."""

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .coordinator import DioChaconDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]

type DioChaconConfigEntry = ConfigEntry[DioChaconDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DioChaconConfigEntry) -> bool:
    """Set up dio_chacon from a config entry."""

    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    dio_chacon_id = config[CONF_UNIQUE_ID]

    dio_chacon_client: DIOChaconAPIClient = DIOChaconAPIClient(
        username,
        password,
        dio_chacon_id,
    )

    coordinator = DioChaconDataUpdateCoordinator(hass, dio_chacon_client)

    # Register callback for device state notification pushed from the server
    def callback_device_state(data: dict[str, Any]) -> None:
        """Receive callback for device state notification pushed from the server."""

        _LOGGER.debug("Data received from server %s", data)
        coordinator.async_set_updated_data(data)

    dio_chacon_client.set_callback_device_state(callback_device_state)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: DioChaconDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
