"""The Concord232 integration."""

import asyncio

from concord232 import client as concord232_client
import requests
from yarl import URL

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DATA_IMPORT_LOCK, DOMAIN

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

type Concord232ConfigEntry = ConfigEntry[concord232_client.Client]


def build_url(host: str, port: int, use_ssl: bool) -> str:
    """Return the server url for the stored connection settings."""
    # URL.build brackets IPv6 hosts correctly
    return str(URL.build(scheme="https" if use_ssl else "http", host=host, port=port))


async def async_import_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    """Import a platform's YAML configuration through the config flow.

    The alarm and binary sensor platforms set up concurrently and import
    the same server. The lock spans the entire flow, including entry
    registration, so the first import creates the entry and the second
    sees it and merges into it instead of creating a duplicate.
    """
    lock = hass.data.setdefault(DATA_IMPORT_LOCK, asyncio.Lock())
    async with lock:
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )


def _connect(url: str) -> concord232_client.Client:
    """Connect to the server and load the zones the sensors are built from.

    Both platforms poll this client from their own executor threads. The
    server sets no cookies and the client never mutates session headers, so
    sharing one requests.Session is safe.
    """
    client = concord232_client.Client(url)
    # The server returns zones in varying order; unnamed zones would otherwise
    # map to different entities on every start
    client.zones = sorted(client.list_zones(), key=lambda zone: zone["number"])
    client.last_zone_update = dt_util.utcnow()
    return client


async def async_setup_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Set up Concord232 from a config entry."""
    url = build_url(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data.get(CONF_SSL, False)
    )
    try:
        entry.runtime_data = await hass.async_add_executor_job(_connect, url)
    except requests.exceptions.RequestException as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Concord232 at {url}") from ex

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: Concord232ConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Concord232ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
