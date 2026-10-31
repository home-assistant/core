"""Connect The Things Stack to the shared LoRaWAN integration."""

from dataclasses import dataclass

from lorawan_connection import ConnectionUnavailable, Unsubscribe
from lorawan_connection.backend.tts import AuthenticationError, TTSConnection
from yarl import URL

from homeassistant.components import lorawan
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_APPLICATION_IDS, CONF_ENDPOINT, CONF_IDENTITY_SERVER, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class TheThingsNetworkData:
    """Own transport and registration cleanup."""

    connection: TTSConnection
    unregister: Unsubscribe
    unsubscribe_disconnect: Unsubscribe


type TheThingsNetworkConfigEntry = ConfigEntry[TheThingsNetworkData]


async def async_setup_entry(
    hass: HomeAssistant, entry: TheThingsNetworkConfigEntry
) -> None:
    """Connect and register this entry's selected applications with LoRaWAN."""
    connection = TTSConnection(
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_API_KEY],
        identity_server=entry.data[CONF_IDENTITY_SERVER],
        application_ids=entry.data[CONF_APPLICATION_IDS],
        network_id=entry.entry_id,
    )
    endpoint = URL(entry.data[CONF_ENDPOINT])
    # Hosted TTN serves its console on the default HTTPS port. Self-hosted
    # servers can use any port, so their console address is unknown.
    configuration_url = (
        str(endpoint.with_port(None).with_path("/console/"))
        if endpoint.host and endpoint.host.endswith(".cloud.thethings.network")
        else None
    )
    try:
        await connection.async_connect()
        unregister = await lorawan.async_register_connection(
            hass, entry, connection=connection, configuration_url=configuration_url
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

    @callback
    def disconnected() -> None:
        if not hass.is_stopping:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    unsubscribe_disconnect = connection.on_disconnect(disconnected)
    entry.runtime_data = TheThingsNetworkData(
        connection, unregister, unsubscribe_disconnect
    )

    async def async_stop(_: Event) -> None:
        await async_unload_entry(hass, entry)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: TheThingsNetworkConfigEntry
) -> None:
    """Withdraw the registration before closing the server connection."""
    entry.runtime_data.unsubscribe_disconnect()
    entry.runtime_data.unregister()
    await entry.runtime_data.connection.close()
