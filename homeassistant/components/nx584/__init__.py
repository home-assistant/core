"""Support for NX584 alarm control panels."""

from dataclasses import dataclass

from nx584 import client
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]


@dataclass
class NX584Data:
    """Runtime data for a nx584 config entry."""

    client: client.Client
    url: str


type NX584ConfigEntry = ConfigEntry[NX584Data]


async def async_setup_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> bool:
    """Set up nx584 from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    url = f"http://{host}:{port}"
    alarm_client = client.Client(url)

    try:
        await hass.async_add_executor_job(alarm_client.list_zones)
    except requests.exceptions.ConnectionError as ex:
        raise ConfigEntryNotReady(f"Unable to connect to {url}") from ex

    entry.runtime_data = NX584Data(client=alarm_client, url=url)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="NX584",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NX584ConfigEntry) -> bool:
    """Unload a nx584 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
