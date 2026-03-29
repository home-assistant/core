"""The UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import ApiAuthError, ApiConnectionError, UnifiAccessApiClient

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: UnifiAccessConfigEntry) -> bool:
    """Set up UniFi Access from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL])

    client = UnifiAccessApiClient(
        host=entry.data[CONF_HOST],
        api_token=entry.data[CONF_API_TOKEN],
        session=session,
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    try:
        await client.authenticate()
    except ApiAuthError as err:
        raise ConfigEntryAuthFailed(
            f"Authentication failed for UniFi Access at {entry.data[CONF_HOST]}"
        ) from err
    except ApiConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to UniFi Access at {entry.data[CONF_HOST]}"
        ) from err

    coordinator = UnifiAccessCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    _remove_stale_devices(hass, entry, coordinator)

    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UnifiAccessConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _remove_stale_devices(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    coordinator: UnifiAccessCoordinator,
) -> None:
    """Remove devices for doors that no longer exist on the hub."""
    device_registry = dr.async_get(hass)
    current_ids = {*coordinator.data.doors, entry.entry_id}
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(
            identifier[0] == DOMAIN and identifier[1] in current_ids
            for identifier in device.identifiers
        ):
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=entry.entry_id,
            )


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: UnifiAccessConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a device from a config entry."""
    coordinator = config_entry.runtime_data
    return not device_entry.identifiers.intersection(
        {
            (DOMAIN, entry_id)
            for entry_id in (*coordinator.data.doors, config_entry.entry_id)
        }
    )
