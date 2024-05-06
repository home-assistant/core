"""The Overkiz (by Somfy) integration."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from aiohttp import ClientError
from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.enums import APIType, OverkizState, UIClass, UIWidget
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    NotSuchTokenException,
    TooManyRequestsException,
)
from pyoverkiz.models import Device, OverkizServer, Scenario
from pyoverkiz.utils import generate_local_server

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_API_TYPE,
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
    client: OverkizClient | None = None
    api_type = entry.data.get(CONF_API_TYPE, APIType.CLOUD)

    # Local API
    if api_type == APIType.LOCAL:
        client = create_local_client(
            hass,
            host=entry.data[CONF_HOST],
            token=entry.data[CONF_TOKEN],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        )

    # Overkiz Cloud API
    else:
        client = create_cloud_client(
            hass,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            server=SUPPORTED_SERVERS[entry.data[CONF_HUB]],
        )

    await _async_migrate_entries(hass, entry)

    try:
        await client.login()
        setup = await client.get_setup()

        # Local API does expose scenarios, but they are not functional.
        # Tracked in https://github.com/Somfy-Developer/Somfy-TaHoma-Developer-Mode/issues/21
        if api_type == APIType.CLOUD:
            scenarios = await client.get_scenarios()
        else:
            scenarios = []
    except (BadCredentialsException, NotSuchTokenException) as exception:
        raise ConfigEntryAuthFailed("Invalid authentication") from exception
    except TooManyRequestsException as exception:
        raise ConfigEntryNotReady("Too many requests, try again later") from exception
    except (TimeoutError, ClientError) as exception:
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
            manufacturer=client.server.manufacturer,
            name=gateway.type.beautify_name if gateway.type else gateway.id,
            sw_version=gateway.connectivity.protocol_version,
            configuration_url=client.server.configuration_url,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entries to new unique IDs."""
    entity_registry = er.async_get(hass)

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        # Python 3.11 treats (str, Enum) and StrEnum in a different way
        # Since pyOverkiz switched to StrEnum, we need to rewrite the unique ids once to the new style
        #
        # io://xxxx-xxxx-xxxx/3541212-OverkizState.CORE_DISCRETE_RSSI_LEVEL -> io://xxxx-xxxx-xxxx/3541212-core:DiscreteRSSILevelState
        # internal://xxxx-xxxx-xxxx/alarm/0-UIWidget.TSKALARM_CONTROLLER -> internal://xxxx-xxxx-xxxx/alarm/0-TSKAlarmController
        # io://xxxx-xxxx-xxxx/xxxxxxx-UIClass.ON_OFF -> io://xxxx-xxxx-xxxx/xxxxxxx-OnOff
        if (key := entry.unique_id.split("-")[-1]).startswith(
            ("OverkizState", "UIWidget", "UIClass")
        ):
            state = key.split(".")[1]
            new_key = ""

            if key.startswith("UIClass"):
                new_key = UIClass[state]
            elif key.startswith("UIWidget"):
                new_key = UIWidget[state]
            else:
                new_key = OverkizState[state]

            new_unique_id = entry.unique_id.replace(key, new_key)

            LOGGER.debug(
                "Migrating entity '%s' unique_id from '%s' to '%s'",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
            )

            if existing_entity_id := entity_registry.async_get_entity_id(
                entry.domain, entry.platform, new_unique_id
            ):
                LOGGER.debug(
                    "Cannot migrate to unique_id '%s', already exists for '%s'. Entity will be removed",
                    new_unique_id,
                    existing_entity_id,
                )
                entity_registry.async_remove(entry.entity_id)

                return None

            return {
                "new_unique_id": new_unique_id,
            }

        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    return True


def create_local_client(
    hass: HomeAssistant, host: str, token: str, verify_ssl: bool
) -> OverkizClient:
    """Create Overkiz local client."""
    session = async_create_clientsession(hass, verify_ssl=verify_ssl)

    return OverkizClient(
        username="",
        password="",
        token=token,
        session=session,
        server=generate_local_server(host=host),
        verify_ssl=verify_ssl,
    )


def create_cloud_client(
    hass: HomeAssistant, username: str, password: str, server: OverkizServer
) -> OverkizClient:
    """Create Overkiz cloud client."""
    # To allow users with multiple accounts/hubs, we create a new session so they have separate cookies
    session = async_create_clientsession(hass)

    return OverkizClient(
        username=username, password=password, session=session, server=server
    )
