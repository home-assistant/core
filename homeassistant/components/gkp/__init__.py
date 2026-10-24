"""The GKP integration."""

from dataclasses import dataclass
import logging

from gkphomepython import GkpAuth, GkpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .coordinator import GkpDeviceCoordinator, GkpDeviceData, GkpHubCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


@dataclass
class GkpRuntimeData:
    """Runtime data for GKP integration."""

    hub_coordinator: GkpHubCoordinator
    device_coordinators: dict[str, GkpDeviceCoordinator]
    client: GkpClient


type GkpConfigEntry = ConfigEntry[GkpRuntimeData]


@callback
def _create_device_coordinators(
    hass: HomeAssistant,
    entry: GkpConfigEntry,
    hub_coordinator: GkpHubCoordinator,
    client: GkpClient,
    device_coordinators: dict[str, GkpDeviceCoordinator],
) -> list[str]:
    """Create coordinators for devices without one, return their IDs."""
    new_device_ids: list[str] = []
    for device_id, thermostat in hub_coordinator.data.items():
        if device_id in device_coordinators:
            continue

        device_coordinator = GkpDeviceCoordinator(
            hass, client, entry, hub_coordinator, device_id
        )
        device_coordinator.async_set_updated_data(GkpDeviceData(thermostat=thermostat))
        device_coordinators[device_id] = device_coordinator
        new_device_ids.append(device_id)

        _LOGGER.debug("Created device coordinator for device %s", device_id)

    return new_device_ids


@callback
def _handle_new_devices(
    hass: HomeAssistant,
    entry: GkpConfigEntry,
    hub_coordinator: GkpHubCoordinator,
) -> None:
    """Check for new devices and create coordinators."""
    new_device_ids = _create_device_coordinators(
        hass,
        entry,
        hub_coordinator,
        entry.runtime_data.client,
        entry.runtime_data.device_coordinators,
    )
    if not new_device_ids:
        return

    _LOGGER.info("Discovered %d new device(s): %s", len(new_device_ids), new_device_ids)
    async_dispatcher_send(hass, f"{DOMAIN}_{entry.entry_id}_new_device")


async def async_setup_entry(hass: HomeAssistant, entry: GkpConfigEntry) -> None:
    """Set up GKP from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    await oauth_session.async_ensure_token_valid()

    client = GkpClient(
        GkpAuth(oauth_session), aiohttp_client.async_get_clientsession(hass)
    )
    hub_coordinator = GkpHubCoordinator(hass, client, entry)

    await hub_coordinator.async_config_entry_first_refresh()

    device_coordinators: dict[str, GkpDeviceCoordinator] = {}
    _create_device_coordinators(
        hass, entry, hub_coordinator, client, device_coordinators
    )

    entry.runtime_data = GkpRuntimeData(
        hub_coordinator=hub_coordinator,
        device_coordinators=device_coordinators,
        client=client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hub_coordinator.async_add_listener(
            lambda: _handle_new_devices(hass, entry, hub_coordinator)
        )
    )


async def async_unload_entry(hass: HomeAssistant, entry: GkpConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
