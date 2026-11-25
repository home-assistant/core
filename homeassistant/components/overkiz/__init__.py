"""The Overkiz (by Somfy) integration."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from aiohttp import ClientError
from pyoverkiz.action_queue import ActionQueueSettings
from pyoverkiz.auth.credentials import (
    LocalTokenCredentials,
    RexelTokenCredentials,
    SomfyTokenCredentials,
    UsernamePasswordCredentials,
)
from pyoverkiz.client import OverkizClient, OverkizClientSettings
from pyoverkiz.const import REXEL_OAUTH_CLIENT_ID
from pyoverkiz.enums import (
    APIType,
    OverkizCommand,
    OverkizState,
    Server,
    UIClass,
    UIWidget,
)
from pyoverkiz.exceptions import (
    BadCredentialsError,
    MaintenanceError,
    NoSuchTokenError,
    NotAuthenticatedError,
    ServiceUnavailableError,
    SomfyServiceError,
    TooManyRequestsError,
)
from pyoverkiz.models import Device, PersistedActionGroup, Place, Setup
from pyoverkiz.utils import create_local_server_config

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    API_RETRY_INTERVAL,
    CONF_API_TYPE,
    CONF_GATEWAY_ID,
    CONF_HUB,
    CONF_LOCAL_API,
    CONF_REFRESH_TOKEN,
    CONF_SITE_OID,
    DOMAIN,
    LOGGER,
    OVERKIZ_DEVICE_TO_PLATFORM,
    PLATFORMS,
    UPDATE_INTERVAL_ALL_ASSUMED_STATE,
    UPDATE_INTERVAL_LOCAL,
    UPDATE_INTERVAL_SAUTER_SMART_CONTROL,
)
from .coordinator import OverkizDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class HomeAssistantOverkizData:
    """Overkiz data stored in the runtime data object."""

    coordinator: OverkizDataUpdateCoordinator
    # A cloud entry can also use the local API, for the devices exposed by it
    local_coordinator: OverkizDataUpdateCoordinator | None
    platforms: defaultdict[Platform, list[Device]]
    scenarios: list[PersistedActionGroup]

    @property
    def devices(self) -> list[Device]:
        """Return the devices of all coordinators."""
        if self.local_coordinator is None:
            return list(self.coordinator.data.values())

        return [
            *self.coordinator.data.values(),
            *self.local_coordinator.data.values(),
        ]

    def coordinator_for(self, device: Device) -> OverkizDataUpdateCoordinator:
        """Return the coordinator that handles the device."""
        if (
            self.local_coordinator is not None
            and device.device_url in self.local_coordinator.data
        ):
            return self.local_coordinator

        return self.coordinator


type OverkizDataConfigEntry = ConfigEntry[HomeAssistantOverkizData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Overkiz component."""
    async_setup_services(hass)

    # Auto-import Rexel's fixed public OAuth2 client (PKCE, no secret).
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(REXEL_OAUTH_CLIENT_ID, "", name="Rexel"),
    )

    return True


async def create_client(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> OverkizClient:
    """Create the Overkiz client matching the API type of a config entry."""
    # Local API
    if entry.data.get(CONF_API_TYPE, APIType.CLOUD) == APIType.LOCAL:
        return create_local_client(
            hass,
            host=entry.data[CONF_HOST],
            token=entry.data[CONF_TOKEN],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        )

    # Rexel Cloud API (OAuth2)
    if entry.data.get(CONF_HUB) == Server.REXEL:
        return await create_rexel_client(hass, entry)

    # Somfy multi-account Cloud API (resumable token)
    if entry.data.get(CONF_HUB) == Server.SOMFY:
        return await create_somfy_client(hass, entry)

    # Overkiz Cloud API
    return create_cloud_client(
        hass,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        server=entry.data[CONF_HUB],
    )


def create_additional_local_client(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> OverkizClient | None:
    """Create the local client that a cloud entry uses next to its cloud client."""
    if (local_api := entry.data.get(CONF_LOCAL_API)) is None:
        return None

    return create_local_client(
        hass,
        host=local_api[CONF_HOST],
        token=local_api[CONF_TOKEN],
        verify_ssl=local_api[CONF_VERIFY_SSL],
    )


async def async_setup_entry(hass: HomeAssistant, entry: OverkizDataConfigEntry) -> None:
    """Set up Overkiz from a config entry."""
    api_type = entry.data.get(CONF_API_TYPE, APIType.CLOUD)
    client = await create_client(hass, entry)

    if (local_client := create_additional_local_client(hass, entry)) is None:
        setup, scenarios = await _async_login_and_get_setup(client, api_type)
        coordinator = await _async_create_coordinator(
            hass, entry, client, api_type, setup, setup.devices
        )
        local_coordinator = None
    else:
        (
            coordinator,
            local_coordinator,
            setup,
            scenarios,
        ) = await _async_create_cloud_and_local_coordinators(
            hass, entry, client, local_client
        )

    entry.runtime_data = data = HomeAssistantOverkizData(
        coordinator=coordinator,
        local_coordinator=local_coordinator,
        platforms=defaultdict(list),
        scenarios=scenarios,
    )

    # Map Overkiz entities to Home Assistant platform
    for device in data.devices:
        if platform := OVERKIZ_DEVICE_TO_PLATFORM.get(
            device.widget
        ) or OVERKIZ_DEVICE_TO_PLATFORM.get(device.ui_class):
            data.platforms[platform].append(device)

    device_registry = dr.async_get(hass)
    server_config = coordinator.client.server_config

    registered_gateway_ids = {gateway.id for gateway in setup.gateways}

    for gateway in setup.gateways:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway.id)},
            model=gateway.type.beautify_name if gateway.type else None,
            model_id=str(gateway.type),
            manufacturer=server_config.manufacturer,
            name=gateway.type.beautify_name if gateway.type else gateway.id,
            sw_version=gateway.connectivity.protocol_version,
            hw_version=f"{gateway.type}:{gateway.sub_type}"
            if gateway.type and gateway.sub_type
            else None,
            configuration_url=server_config.configuration_url,
        )

    # Some devices reference a gateway that is not part of setup.gateways
    # (e.g. a secondary box hosting a device). Register a device for each such
    # gateway so the via_device link of its child devices resolves.
    for gateway_id in {
        device.identifier.gateway_id for device in data.devices
    } - registered_gateway_ids:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway_id)},
            manufacturer=server_config.manufacturer,
            name=gateway_id,
            configuration_url=server_config.configuration_url,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_login_and_get_setup(
    client: OverkizClient, api_type: APIType
) -> tuple[Setup, list[PersistedActionGroup]]:
    """Log in and return the setup and the scenarios of an API."""
    try:
        await client.login()
        setup = await client.get_setup()

        # Local API does expose scenarios, but they are not functional.
        # Tracked in https://github.com/Somfy-Developer/Somfy-TaHoma-Developer-Mode/issues/21
        if api_type == APIType.CLOUD:
            scenarios = await client.get_action_groups()
        else:
            scenarios = []
    except (
        BadCredentialsError,
        NoSuchTokenError,
        NotAuthenticatedError,
        OAuth2TokenRequestReauthError,
    ) as exception:
        raise ConfigEntryAuthFailed("Invalid authentication") from exception
    except TooManyRequestsError as exception:
        raise ConfigEntryNotReady("Too many requests, try again later") from exception
    except OAuth2TokenRequestError as exception:
        raise ConfigEntryNotReady("Failed to refresh OAuth2 token") from exception
    except (TimeoutError, ClientError) as exception:
        raise ConfigEntryNotReady("Failed to connect") from exception
    except MaintenanceError as exception:
        raise ConfigEntryNotReady("Server is down for maintenance") from exception
    except ServiceUnavailableError as exception:
        raise ConfigEntryNotReady("Server is unavailable") from exception
    except SomfyServiceError as exception:
        raise ConfigEntryNotReady("Somfy service error") from exception

    return setup, scenarios


async def _async_create_coordinator(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    client: OverkizClient,
    api_type: APIType,
    setup: Setup,
    devices: list[Device],
    *,
    places: Place | None = None,
    excluded_device_urls: frozenset[str] = frozenset(),
) -> OverkizDataUpdateCoordinator:
    """Create the coordinator that handles the given devices through an API."""
    coordinator = OverkizDataUpdateCoordinator(
        hass,
        entry,
        LOGGER,
        client=client,
        devices=devices,
        gateways=setup.gateways,
        places=places or setup.root_place,
        excluded_device_urls=excluded_device_urls,
    )

    await coordinator.async_config_entry_first_refresh()

    if coordinator.is_stateless:
        LOGGER.debug(
            "All devices have an assumed state."
            " Update interval has been reduced to: %s",
            UPDATE_INTERVAL_ALL_ASSUMED_STATE,
        )
        coordinator.set_update_interval(UPDATE_INTERVAL_ALL_ASSUMED_STATE)

    if api_type == APIType.LOCAL:
        LOGGER.debug(
            "Devices connect via Local API. Update interval has been reduced to: %s",
            UPDATE_INTERVAL_LOCAL,
        )
        coordinator.set_update_interval(UPDATE_INTERVAL_LOCAL)
    elif entry.data[CONF_HUB] == Server.SAUTER_SMART_CONTROL:
        LOGGER.debug(
            "Sauter Smart Control listening sessions expire within 30 seconds."
            " Update interval has been reduced to: %s",
            UPDATE_INTERVAL_SAUTER_SMART_CONTROL,
        )
        coordinator.set_update_interval(UPDATE_INTERVAL_SAUTER_SMART_CONTROL)

    return coordinator


async def _async_create_cloud_and_local_coordinators(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    cloud_client: OverkizClient,
    local_client: OverkizClient,
) -> tuple[
    OverkizDataUpdateCoordinator,
    OverkizDataUpdateCoordinator | None,
    Setup,
    list[PersistedActionGroup],
]:
    """Create the coordinators of a cloud entry that also uses the local API.

    The local API handles the devices it exposes, the cloud API the other ones.
    If one of both cannot be reached, the other one handles what it can on its
    own and the entry is reloaded once the missing API is back.
    """
    try:
        cloud_setup, scenarios = await _async_login_and_get_setup(
            cloud_client, APIType.CLOUD
        )
    except ConfigEntryNotReady as cloud_error:
        try:
            local_setup, _ = await _async_login_and_get_setup(
                local_client, APIType.LOCAL
            )
            local_coordinator = await _async_create_coordinator(
                hass,
                entry,
                local_client,
                APIType.LOCAL,
                local_setup,
                local_setup.devices,
            )
        except ConfigEntryAuthFailed, ConfigEntryNotReady:
            raise cloud_error from None

        LOGGER.warning(
            "Cloud API cannot be reached, only the devices of the local API are set up"
        )
        _async_reload_once_reachable(hass, entry, cloud_client, APIType.CLOUD)
        return local_coordinator, None, local_setup, []

    try:
        local_setup, _ = await _async_login_and_get_setup(local_client, APIType.LOCAL)
        local_coordinator = await _async_create_coordinator(
            hass,
            entry,
            local_client,
            APIType.LOCAL,
            local_setup,
            local_setup.devices,
            # The local API does not know the places, which become the areas
            places=cloud_setup.root_place,
        )
    except (ConfigEntryAuthFailed, ConfigEntryNotReady) as local_error:
        LOGGER.warning(
            "Local API cannot be used, all devices are set up through the cloud API: %s",
            local_error,
        )
        _async_reload_once_reachable(hass, entry, local_client, APIType.LOCAL)

        coordinator = await _async_create_coordinator(
            hass, entry, cloud_client, APIType.CLOUD, cloud_setup, cloud_setup.devices
        )
        return coordinator, None, cloud_setup, scenarios

    local_device_urls = frozenset(device.device_url for device in local_setup.devices)

    try:
        coordinator = await _async_create_coordinator(
            hass,
            entry,
            cloud_client,
            APIType.CLOUD,
            cloud_setup,
            [
                device
                for device in cloud_setup.devices
                if device.device_url not in local_device_urls
            ],
            excluded_device_urls=local_device_urls,
        )
    except ConfigEntryNotReady:
        LOGGER.warning(
            "Cloud API cannot be reached, only the devices of the local API are set up"
        )
        _async_reload_once_reachable(hass, entry, cloud_client, APIType.CLOUD)
        return local_coordinator, None, local_setup, []

    return coordinator, local_coordinator, cloud_setup, scenarios


@callback
def _async_reload_once_reachable(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    client: OverkizClient,
    api_type: APIType,
) -> None:
    """Reload the entry once the API that failed during setup can be used."""

    async def _async_reload_if_reachable() -> None:
        try:
            await _async_login_and_get_setup(client, api_type)
        except ConfigEntryNotReady:
            return
        except ConfigEntryAuthFailed:
            if api_type == APIType.LOCAL:
                return
            # Setting up the entry again asks for the cloud credentials
        else:
            LOGGER.info("%s API can be used again", api_type.name.capitalize())

        hass.config_entries.async_schedule_reload(entry.entry_id)

    @callback
    def _async_try_api(now: datetime) -> None:
        # A task of the entry is cancelled when the entry is unloaded
        entry.async_create_background_task(
            hass, _async_reload_if_reachable(), f"overkiz_{api_type}_api_retry"
        )

    entry.async_on_unload(
        async_track_time_interval(hass, _async_try_api, API_RETRY_INTERVAL)
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> None:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 2:
        await _async_migrate_strenum_unique_ids(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    if entry.version == 1 and entry.minor_version < 3:
        entity_registry = er.async_get(hass)
        legacy_suffix = f"-{OverkizCommand.GO_TO_ALIAS}"
        legacy_buttons = [
            entity_entry
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if entity_entry.domain == Platform.BUTTON
            and entity_entry.unique_id.endswith(legacy_suffix)
        ]

        # The legacy button hardcoded alias id 1, which is the favorite1 ("My
        # position") slot. Devices advertising any other type never had a working
        # button, so those entities have no counterpart to migrate to.
        devices_with_favorite: set[str] = set()
        if legacy_buttons:
            # Whether a legacy button has a counterpart depends on the aliases the
            # device advertises, so this needs the devices from the API.
            client = await create_client(hass, entry)
            try:
                await client.login(register_event_listener=False)
                setup = await client.get_setup()
            except (
                BadCredentialsError,
                NoSuchTokenError,
                NotAuthenticatedError,
                OAuth2TokenRequestReauthError,
            ):
                # Reauth is not started for a failed migration, so drop the legacy
                # buttons instead of blocking setup, which then starts reauth.
                LOGGER.warning(
                    "Could not authenticate to migrate goToAlias buttons, removing them"
                )
            except (
                TooManyRequestsError,
                OAuth2TokenRequestError,
                TimeoutError,
                ClientError,
                MaintenanceError,
                ServiceUnavailableError,
                SomfyServiceError,
            ) as exception:
                raise ConfigEntryNotReady(
                    "Failed to fetch devices for migration"
                ) from exception
            else:
                devices_with_favorite = {
                    device.device_url
                    for device in setup.devices
                    if any(
                        alias.type == "favorite1"
                        for alias in device.get_supported_aliases()
                    )
                }

        for entity_entry in legacy_buttons:
            if entity_entry.unique_id.removesuffix(legacy_suffix) in (
                devices_with_favorite
            ):
                new_unique_id = f"{entity_entry.unique_id}_favorite1"
                LOGGER.debug(
                    "Migrating entity '%s' unique_id from '%s' to '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                    new_unique_id,
                )
                entity_registry.async_update_entity(
                    entity_entry.entity_id, new_unique_id=new_unique_id
                )
                continue

            LOGGER.debug(
                "Removing entity '%s', device does not expose a favorite1 alias",
                entity_entry.entity_id,
            )
            entity_registry.async_remove(entity_entry.entity_id)

        hass.config_entries.async_update_entry(entry, minor_version=3)


async def _async_migrate_strenum_unique_ids(
    hass: HomeAssistant, config_entry: OverkizDataConfigEntry
) -> None:
    """Migrate entities to the StrEnum-style unique IDs."""
    entity_registry = er.async_get(hass)

    # Map enum members renamed in pyoverkiz 2.0 to their current names.
    renamed_enum_members = {"TSKALARM_CONTROLLER": "TSK_ALARM_CONTROLLER"}

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        # Python 3.11 treats (str, Enum) and StrEnum
        # differently. Since pyOverkiz switched to StrEnum, we
        # need to rewrite the unique ids once to the new style.
        #
        # OverkizState.CORE_DISCRETE_RSSI_LEVEL
        #   -> core:DiscreteRSSILevelState
        # UIWidget.TSKALARM_CONTROLLER
        #   -> TSKAlarmController
        # UIClass.ON_OFF -> OnOff
        if (key := entry.unique_id.split("-")[-1]).startswith(
            ("OverkizState", "UIWidget", "UIClass")
        ):
            state = key.split(".")[1]
            state = renamed_enum_members.get(state, state)
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
                    "Cannot migrate to unique_id '%s', already"
                    " exists for '%s'. Entity will be removed",
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


def create_local_client(
    hass: HomeAssistant, host: str, token: str, verify_ssl: bool
) -> OverkizClient:
    """Create Overkiz local client."""
    session = async_create_clientsession(hass, verify_ssl=verify_ssl)

    return OverkizClient(
        server=create_local_server_config(host=host),
        credentials=LocalTokenCredentials(token),
        session=session,
        verify_ssl=verify_ssl,
        settings=OverkizClientSettings(
            action_queue=ActionQueueSettings(), default_rts_command_duration=0
        ),
    )


def create_cloud_client(
    hass: HomeAssistant, username: str, password: str, server: Server
) -> OverkizClient:
    """Create Overkiz cloud client."""
    # To allow users with multiple accounts/hubs, we create a
    # new session so they have separate cookies
    session = async_create_clientsession(hass)

    return OverkizClient(
        server=server,
        credentials=UsernamePasswordCredentials(username, password),
        session=session,
        settings=OverkizClientSettings(
            action_queue=ActionQueueSettings(), default_rts_command_duration=0
        ),
    )


async def create_rexel_client(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> OverkizClient:
    """Create Overkiz Rexel client backed by a Home Assistant OAuth2 session."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def async_get_token() -> str:
        """Return a valid access token, refreshing and persisting as needed."""
        await oauth_session.async_ensure_token_valid()
        return cast(str, oauth_session.token["access_token"])

    return OverkizClient(
        server=Server.REXEL,
        credentials=RexelTokenCredentials(
            access_token_callback=async_get_token,
            gateway_id=entry.data[CONF_GATEWAY_ID],
        ),
        session=async_create_clientsession(hass),
        settings=OverkizClientSettings(
            action_queue=ActionQueueSettings(), default_rts_command_duration=0
        ),
    )


async def create_somfy_client(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> OverkizClient:
    """Create an Overkiz client for a Somfy multi-account, resumed from a token."""

    async def on_token_refresh(refresh_token: str) -> None:
        """Persist the rotated Somfy refresh token back to the config entry."""
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )

    return OverkizClient(
        server=Server.SOMFY,
        credentials=SomfyTokenCredentials(
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            site_oid=entry.data[CONF_SITE_OID],
            region=entry.data[CONF_REGION],
            gateway_id=entry.data[CONF_GATEWAY_ID],
            on_token_refresh=on_token_refresh,
        ),
        session=async_create_clientsession(hass),
        settings=OverkizClientSettings(
            action_queue=ActionQueueSettings(), default_rts_command_duration=0
        ),
    )
