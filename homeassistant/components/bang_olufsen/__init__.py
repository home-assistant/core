"""The Bang & Olufsen integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import (
    ClientConnectorError,
    ClientOSError,
    ServerTimeoutError,
    WSMessageTypeError,
)
from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util.ssl import get_default_context

from .const import DOMAIN, MANUFACTURER, BangOlufsenModel
from .util import get_remotes
from .websocket import BangOlufsenWebsocket


@dataclass
class BangOlufsenData:
    """Dataclass for API client and WebSocket client."""

    websocket: BangOlufsenWebsocket
    client: MozartClient


type BangOlufsenConfigEntry = ConfigEntry[BangOlufsenData]

PLATFORMS = [Platform.EVENT, Platform.MEDIA_PLAYER]


async def _handle_remote_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, client: MozartClient
) -> None:
    """Add or remove paired Beoremote One devices."""
    # Check for connected Beoremote One remotes
    if remotes := await get_remotes(client):
        for remote in remotes:
            if TYPE_CHECKING:
                assert remote.serial_number
                assert config_entry.unique_id

            # Create Beoremote One device
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                identifiers={(DOMAIN, remote.serial_number)},
                name=f"{BangOlufsenModel.BEOREMOTE_ONE}-{remote.serial_number}",
                model=BangOlufsenModel.BEOREMOTE_ONE,
                serial_number=remote.serial_number,
                sw_version=remote.app_version,
                manufacturer=MANUFACTURER,
                via_device=(DOMAIN, config_entry.unique_id),
            )

    # If the remote is no longer available, then delete the device.
    # The remote may appear as being available to the device after has been unpaired on the remote
    # As it has to be removed from the device on the app.

    device_registry = dr.async_get(hass)
    devices = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )
    for device in devices:
        if (
            device.model == BangOlufsenModel.BEOREMOTE_ONE
            and device.serial_number not in [remote.serial_number for remote in remotes]
        ):
            device_registry.async_remove_device(device.id)


async def async_setup_entry(hass: HomeAssistant, entry: BangOlufsenConfigEntry) -> bool:
    """Set up from a config entry."""

    # Remove casts to str
    assert entry.unique_id

    # Create device now as BangOlufsenWebsocket needs a device for debug logging, firing events etc.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name=entry.title,
        model=entry.data[CONF_MODEL],
    )

    client = MozartClient(host=entry.data[CONF_HOST], ssl_context=get_default_context())

    # Check API and WebSocket connection
    try:
        await client.check_device_connection(True)
    except* (
        ClientConnectorError,
        ClientOSError,
        ServerTimeoutError,
        ApiException,
        TimeoutError,
        WSMessageTypeError,
    ) as error:
        await client.close_api_client()
        raise ConfigEntryNotReady(f"Unable to connect to {entry.title}") from error

    websocket = BangOlufsenWebsocket(hass, entry, client)

    # Add the websocket and API client
    entry.runtime_data = BangOlufsenData(websocket, client)

    # Handle paired Beoremote One devices
    await _handle_remote_devices(hass, entry, client)

    # Start WebSocket connection
    await client.connect_notifications(remote_control=True, reconnect=True)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BangOlufsenConfigEntry
) -> bool:
    """Unload a config entry."""
    # Close the API client and WebSocket notification listener
    entry.runtime_data.client.disconnect_notifications()
    await entry.runtime_data.client.close_api_client()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
