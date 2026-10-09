"""The GKP integration."""

from dataclasses import dataclass
from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError
from gkphomepython import GkpAuth, GkpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import GkpDeviceCoordinator, GkpDeviceData, GkpHubCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GKP component."""
    async_setup_services(hass)
    return True


@dataclass
class GkpRuntimeData:
    """Runtime data for GKP integration."""

    auth: GkpAuth
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


async def async_setup_entry(hass: HomeAssistant, entry: GkpConfigEntry) -> bool:
    """Set up GKP from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await oauth_session.async_ensure_token_valid()
    except ClientResponseError as err:
        if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="oauth_session_not_valid",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="temporary_connection_error",
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="network_issue",
        ) from err

    auth = GkpAuth(oauth_session)
    client = GkpClient(auth, aiohttp_client.async_get_clientsession(hass))
    hub_coordinator = GkpHubCoordinator(hass, client, entry)

    await hub_coordinator.async_config_entry_first_refresh()

    device_coordinators: dict[str, GkpDeviceCoordinator] = {}
    _create_device_coordinators(
        hass, entry, hub_coordinator, client, device_coordinators
    )

    entry.runtime_data = GkpRuntimeData(
        auth=auth,
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GkpConfigEntry) -> bool:
    """Unload a config entry."""
    for device_coordinator in entry.runtime_data.device_coordinators.values():
        device_coordinator.unsubscribe_hub_listener()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
