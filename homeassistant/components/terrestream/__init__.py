"""Local sensors for Terrestream."""

from terrestream_local import Client, Credentials
from terrestream_local.errors import AuthenticationError, ClientError

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import TerrestreamConfigEntry, TerrestreamCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TerrestreamConfigEntry) -> None:
    """Authenticate the sensor before loading entities."""
    client = Client(
        async_get_clientsession(hass),
        entry.data["host"],
        Credentials(**entry.data["credentials"]),
    )
    try:
        identity = await client.identity()
        if not identity["paired"]:
            await client.confirm()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="pairing_revoked"
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    coordinator = TerrestreamCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_release)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def release_on_stop(event: Event) -> None:
        await coordinator.async_release()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, release_on_stop)
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: TerrestreamConfigEntry
) -> None:
    """Unload entities and release controller ownership."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
