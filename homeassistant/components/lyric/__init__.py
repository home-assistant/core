"""The Honeywell Lyric integration."""

from aiolyric import Lyric

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)

from .api import (
    ConfigEntryLyricClient,
    LyricLocalOAuth2Implementation,
    OAuth2SessionLyric,
)
from .const import DOMAIN
from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import create_thermostat_device_info

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LyricConfigEntry) -> bool:
    """Set up Honeywell Lyric from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    if not isinstance(implementation, LyricLocalOAuth2Implementation):
        raise TypeError("Unexpected auth implementation; can't find oauth client id")

    session = aiohttp_client.async_get_clientsession(hass)
    oauth_session = OAuth2SessionLyric(hass, entry, implementation)

    client = ConfigEntryLyricClient(session, oauth_session)

    client_id = implementation.client_id
    lyric = Lyric(client, client_id)

    coordinator = LyricDataUpdateCoordinator(
        hass,
        config_entry=entry,
        oauth_session=oauth_session,
        lyric=lyric,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the thermostat devices up front so the accessory (room sensor)
    # entities can resolve them as their via_device parent regardless of the
    # order the platforms are set up in.
    device_registry = dr.async_get(hass)
    for location in coordinator.data.locations:
        for device in location.devices:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **create_thermostat_device_info(device),
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LyricConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
