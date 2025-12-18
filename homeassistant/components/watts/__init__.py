"""The Watts Vision + integration."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError
from visionpluspython.auth import WattsVisionAuth
from visionpluspython.client import WattsVisionClient
from visionpluspython.models import ThermostatDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .coordinator import (
    WattsVisionHubCoordinator,
    WattsVisionThermostatCoordinator,
    WattsVisionThermostatData,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


@dataclass
class WattsVisionRuntimeData:
    """Runtime data for Watts Vision integration."""

    auth: WattsVisionAuth
    hub_coordinator: WattsVisionHubCoordinator
    thermostat_coordinators: dict[str, WattsVisionThermostatCoordinator]
    client: WattsVisionClient


type WattsVisionConfigEntry = ConfigEntry[WattsVisionRuntimeData]


@callback
def _handle_new_thermostats(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    hub_coordinator: WattsVisionHubCoordinator,
) -> None:
    """Check for new thermostat devices and create coordinators."""

    current_device_ids = set(hub_coordinator.data.keys())
    known_device_ids = set(entry.runtime_data.thermostat_coordinators.keys())
    new_device_ids = current_device_ids - known_device_ids

    if not new_device_ids:
        return

    _LOGGER.info("Discovered %d new device(s): %s", len(new_device_ids), new_device_ids)

    thermostat_coordinators = entry.runtime_data.thermostat_coordinators
    client = entry.runtime_data.client

    for device_id in new_device_ids:
        device = hub_coordinator.data[device_id]
        if not isinstance(device, ThermostatDevice):
            continue

        thermostat_coordinator = WattsVisionThermostatCoordinator(
            hass, client, entry, hub_coordinator, device_id
        )
        thermostat_coordinator.async_set_updated_data(
            WattsVisionThermostatData(thermostat=device)
        )
        thermostat_coordinators[device_id] = thermostat_coordinator

        _LOGGER.debug("Created thermostat coordinator for device %s", device_id)

    async_dispatcher_send(hass, f"{DOMAIN}_{entry.entry_id}_new_device")


async def async_setup_entry(hass: HomeAssistant, entry: WattsVisionConfigEntry) -> bool:
    """Set up Watts Vision from a config entry."""

    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except config_entry_oauth2_flow.ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable"
        ) from err

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await oauth_session.async_ensure_token_valid()
    except ClientResponseError as err:
        if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ConfigEntryAuthFailed("OAuth session not valid") from err
        raise ConfigEntryNotReady("Temporary connection error") from err
    except ClientError as err:
        raise ConfigEntryNotReady("Network issue during OAuth setup") from err

    session = aiohttp_client.async_get_clientsession(hass)
    auth = WattsVisionAuth(
        oauth_session=oauth_session,
        session=session,
    )

    client = WattsVisionClient(auth, session)
    hub_coordinator = WattsVisionHubCoordinator(hass, client, entry)

    await hub_coordinator.async_config_entry_first_refresh()

    thermostat_coordinators: dict[str, WattsVisionThermostatCoordinator] = {}
    for device_id in hub_coordinator.device_ids:
        device = hub_coordinator.data[device_id]
        if not isinstance(device, ThermostatDevice):
            continue

        thermostat_coordinator = WattsVisionThermostatCoordinator(
            hass, client, entry, hub_coordinator, device_id
        )
        thermostat_coordinator.async_set_updated_data(
            WattsVisionThermostatData(thermostat=device)
        )
        thermostat_coordinators[device_id] = thermostat_coordinator

    entry.runtime_data = WattsVisionRuntimeData(
        auth=auth,
        hub_coordinator=hub_coordinator,
        thermostat_coordinators=thermostat_coordinators,
        client=client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listener for dynamic device detection
    entry.async_on_unload(
        hub_coordinator.async_add_listener(
            lambda: _handle_new_thermostats(hass, entry, hub_coordinator)
        )
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WattsVisionConfigEntry
) -> bool:
    """Unload a config entry."""
    for thermostat_coordinator in entry.runtime_data.thermostat_coordinators.values():
        thermostat_coordinator.unsubscribe_hub_listener()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
