"""Connect an external ChirpStack server to the shared LoRaWAN integration."""

from dataclasses import dataclass

from lorawan_connection import ConnectionUnavailable, Unsubscribe
from lorawan_connection.backend.chirpstack import (
    AuthenticationError,
    ChirpStackConnection,
)

from homeassistant.components import lorawan
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_APPLICATION_IDS, CONF_ENDPOINT, CONF_TENANT_ID, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class ChirpStackData:
    """Own transport and registration cleanup."""

    connection: ChirpStackConnection
    unregister: Unsubscribe
    unsubscribe_disconnect: Unsubscribe


type ChirpStackConfigEntry = ConfigEntry[ChirpStackData]


async def async_setup_entry(hass: HomeAssistant, entry: ChirpStackConfigEntry) -> bool:
    """Connect and register this entry's selected applications with LoRaWAN."""
    connection = ChirpStackConnection(
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_API_KEY],
        tenant_id=entry.data[CONF_TENANT_ID],
        application_ids=entry.data[CONF_APPLICATION_IDS],
        network_id=entry.entry_id,
    )
    try:
        await connection.async_connect()
        unregister = await lorawan.async_register_connection(
            hass, entry, connection=connection
        )
    except AuthenticationError as error:
        await connection.close()
        raise ConfigEntryAuthFailed from error
    except ConnectionUnavailable as error:
        await connection.close()
        raise ConfigEntryNotReady from error
    except BaseException:
        await connection.close()
        raise
    entry.async_on_unload(unregister)

    @callback
    def disconnected() -> None:
        if not hass.is_stopping:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    unsubscribe_disconnect = connection.on_disconnect(disconnected)
    entry.async_on_unload(unsubscribe_disconnect)
    entry.runtime_data = ChirpStackData(connection, unregister, unsubscribe_disconnect)

    async def async_stop(_: Event) -> None:
        unregister()
        await connection.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChirpStackConfigEntry) -> bool:
    """Withdraw the registration before closing the server connection."""
    entry.runtime_data.unsubscribe_disconnect()
    entry.runtime_data.unregister()
    await entry.runtime_data.connection.close()
    return True
