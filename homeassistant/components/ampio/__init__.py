"""The Ampio integration."""

from dataclasses import dataclass
import logging

from ampio_mqtt import (
    AmpioAuthError,
    AmpioClient,
    AmpioConnectionError,
    AmpioNotConfigured,
    AuthFailed,
    AvailabilityChanged,
    ConnectionDied,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, HUB_IDENTIFIER, PLATFORMS

_LOGGER = logging.getLogger(__name__)

type AmpioConfigEntry = ConfigEntry[AmpioData]


@dataclass
class AmpioData:
    """Runtime data for one Ampio server."""

    client: AmpioClient
    hub_device_id: str


async def async_setup_entry(hass: HomeAssistant, entry: AmpioConfigEntry) -> bool:
    """Set up Ampio from a config entry."""
    client = AmpioClient(
        entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    entry.async_on_unload(client.disconnect)

    # Home Assistant does not unload entries when it stops, so without this the
    # connection dies by task cancellation and is reported as a lost connection.
    async def _async_disconnect(event: Event) -> None:
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    # The library dispatches terminal events from the first session on, inside
    # connect(), and does not replay them.
    ended_while_connecting: list[AuthFailed | ConnectionDied] = []
    stop_collecting = client.subscribe(
        ended_while_connecting.append, of=(AuthFailed, ConnectionDied)
    )
    entry.async_on_unload(stop_collecting)

    try:
        discovered = await client.connect()
    except AmpioAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except AmpioNotConfigured as err:
        # The library still serves every other row. Its message embeds
        # Designer names, so only ids reach the log.
        if err.objects:
            _LOGGER.warning(
                "Ampio Designer leaves objects %s without a bus address; fix "
                "them in Ampio Designer",
                ", ".join(str(oid) for oid in sorted(oid for oid, _ in err.objects)),
            )
        discovered = True
    except AmpioConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    stop_collecting()
    if ended_while_connecting:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        )
    # A True connect() guarantees the server identity; the None check narrows the type.
    if not discovered or (info := client.server_info) is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="discovery_timeout"
        )

    hub = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={HUB_IDENTIFIER},
        manufacturer="Ampio",
        name="M-SERV",
        model="M-SERV",
        sw_version=info.server_version,
        serial_number=info.device_id,
        configuration_url=f"http://{info.local_ip}" if info.local_ip else None,
    )
    entry.runtime_data = AmpioData(client, hub.id)

    was_unavailable = False

    @callback
    def _availability_changed(event: AvailabilityChanged) -> None:
        """Log a real outage once on loss and once on restore."""
        nonlocal was_unavailable
        if not event.available:
            was_unavailable = True
            _LOGGER.warning("Connection to the Ampio server lost; reconnecting")
        elif was_unavailable:
            was_unavailable = False
            _LOGGER.info("Connection to the Ampio server restored")

    @callback
    def _connection_ended(event: AuthFailed | ConnectionDied) -> None:
        """Recover from a terminal connection failure by re-running setup.

        Both events mean the library's reconnect loop has stopped for good;
        reloading re-raises a credential rejection as ConfigEntryAuthFailed
        and retries everything else with backoff.
        """
        _LOGGER.error(
            "Connection to the Ampio server ended (%s); reloading", event.reason
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        client.subscribe(_availability_changed, of=AvailabilityChanged)
    )
    entry.async_on_unload(
        client.subscribe(_connection_ended, of=(AuthFailed, ConnectionDied))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmpioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
