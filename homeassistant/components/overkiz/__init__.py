"""The Overkiz (by Somfy) integration."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from aiohttp import ClientError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)
from pyoverkiz.models import Device, Scenario

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_HUB,
    DOMAIN,
    LOGGER,
    OVERKIZ_DEVICE_TO_PLATFORM,
    PLATFORMS,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ALL_ASSUMED_STATE,
)
from .coordinator import OverkizDataUpdateCoordinator


@dataclass
class HomeAssistantOverkizData:
    """Overkiz data stored in the Home Assistant data object."""

    coordinator: OverkizDataUpdateCoordinator
    platforms: defaultdict[Platform, list[Device]]
    scenarios: list[Scenario]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Overkiz from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    server = SUPPORTED_SERVERS[entry.data[CONF_HUB]]

    # To allow users with multiple accounts/hubs, we create a new session so they have separate cookies
    session = async_create_clientsession(hass)
    client = OverkizClient(
        username=username, password=password, session=session, server=server
    )

    try:
        await client.login()

        setup, scenarios = await asyncio.gather(
            *[
                client.get_setup(),
                client.get_scenarios(),
            ]
        )
    except BadCredentialsException as exception:
        raise ConfigEntryAuthFailed("Invalid authentication") from exception
    except TooManyRequestsException as exception:
        raise ConfigEntryNotReady("Too many requests, try again later") from exception
    except (TimeoutError, ClientError, ServerDisconnectedError) as exception:
        raise ConfigEntryNotReady("Failed to connect") from exception
    except MaintenanceException as exception:
        raise ConfigEntryNotReady("Server is down for maintenance") from exception

    coordinator = OverkizDataUpdateCoordinator(
        hass,
        LOGGER,
        name="device events",
        client=client,
        devices=setup.devices,
        places=setup.root_place,
        update_interval=UPDATE_INTERVAL,
        config_entry_id=entry.entry_id,
    )

    await coordinator.async_config_entry_first_refresh()

    if coordinator.is_stateless:
        LOGGER.debug(
            (
                "All devices have an assumed state. Update interval has been reduced"
                " to: %s"
            ),
            UPDATE_INTERVAL_ALL_ASSUMED_STATE,
        )
        coordinator.update_interval = UPDATE_INTERVAL_ALL_ASSUMED_STATE

    platforms: defaultdict[Platform, list[Device]] = defaultdict(list)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantOverkizData(
        coordinator=coordinator, platforms=platforms, scenarios=scenarios
    )

    # Map Overkiz entities to Home Assistant platform
    for device in coordinator.data.values():
        LOGGER.debug(
            (
                "The following device has been retrieved. Report an issue if not"
                " supported correctly (%s)"
            ),
            device,
        )

        if platform := OVERKIZ_DEVICE_TO_PLATFORM.get(
            device.widget
        ) or OVERKIZ_DEVICE_TO_PLATFORM.get(device.ui_class):
            platforms[platform].append(device)

    device_registry = dr.async_get(hass)

    for gateway in setup.gateways:
        LOGGER.debug("Added gateway (%s)", gateway)

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway.id)},
            model=gateway.sub_type.beautify_name if gateway.sub_type else None,
            manufacturer=server.manufacturer,
            name=gateway.type.beautify_name if gateway.type else gateway.id,
            sw_version=gateway.connectivity.protocol_version,
            configuration_url=server.configuration_url,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
