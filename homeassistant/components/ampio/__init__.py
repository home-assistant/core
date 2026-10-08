"""The Ampio integration."""

from dataclasses import dataclass
import logging

from ampio_mqtt import (
    AmpioAdminClient,
    AmpioAuthError,
    AmpioClient,
    AmpioConnectionError,
    AmpioNotConfigured,
    AuthFailed,
    AvailabilityChanged,
    ConnectionDied,
    format_mac,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr

from .const import ADMIN_USERNAME, DOMAIN, HUB_IDENTIFIER, PLATFORMS

_LOGGER = logging.getLogger(__name__)

type AmpioConfigEntry = ConfigEntry[AmpioData]


@dataclass
class AmpioData:
    """Runtime data for one Ampio server."""

    client: AmpioClient
    # The same client when the entry signs in as the administrator, the only
    # account served the module catalogue. None on a standard account.
    admin: AmpioAdminClient | None
    hub_device_id: str


async def async_setup_entry(hass: HomeAssistant, entry: AmpioConfigEntry) -> bool:
    """Set up Ampio from a config entry."""
    admin: AmpioAdminClient | None = None
    client: AmpioClient
    if entry.data[CONF_USERNAME] == ADMIN_USERNAME:
        client = admin = AmpioAdminClient(
            entry.data[CONF_HOST], entry.data[CONF_PASSWORD]
        )
    else:
        client = AmpioClient(
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
    entry.async_on_unload(client.disconnect)

    # Home Assistant does not unload entries when it stops, so without this the
    # connection dies by task cancellation and is reported as a lost connection.
    async def _async_disconnect(event: Event) -> None:
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    try:
        discovered = await client.connect()
    except AmpioAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except AmpioNotConfigured as err:
        # The library still serves every other row. Its message embeds
        # Designer names, so only ids and macs reach the log.
        if err.objects:
            _LOGGER.warning(
                "Ampio Designer leaves objects %s without a bus address; fix "
                "them in Ampio Designer",
                ", ".join(str(oid) for oid in sorted(oid for oid, _ in err.objects)),
            )
        if err.collisions:
            _LOGGER.warning(
                "Ampio Designer leaves module addresses %s without exactly one "
                "module row; fix them in Ampio Designer",
                ", ".join(
                    format_mac(mac) for mac in sorted(mac for mac, _ in err.collisions)
                ),
            )
        discovered = True
    except AmpioConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    # A True connect() guarantees the server identity; the None check narrows the type.
    if not discovered or (info := client.server_info) is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="discovery_timeout"
        )
    # Object ids are unique per server, so another server's objects would
    # bind to this entry's entities.
    if info.server_key != entry.unique_id:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unexpected_device"
        )

    mserv = admin.mserv if admin else None
    hub = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={HUB_IDENTIFIER},
        manufacturer="Ampio",
        name="M-SERV",
        model=mserv.model if mserv and mserv.model else "M-SERV",
        sw_version=info.server_version,
        serial_number=info.device_id,
        configuration_url=f"http://{info.local_ip}" if info.local_ip else None,
    )
    entry.runtime_data = AmpioData(client, admin, hub.id)

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
