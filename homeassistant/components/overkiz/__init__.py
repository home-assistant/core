"""The Overkiz (by Somfy) integration."""

from collections import defaultdict
from dataclasses import dataclass
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
from pyoverkiz.enums import APIType, OverkizState, Server, UIClass, UIWidget
from pyoverkiz.exceptions import (
    BadCredentialsError,
    MaintenanceError,
    NoSuchTokenError,
    NotAuthenticatedError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from pyoverkiz.models import Device, PersistedActionGroup
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
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_TYPE,
    CONF_GATEWAY_ID,
    CONF_HUB,
    CONF_REFRESH_TOKEN,
    CONF_SITE_OID,
    DOMAIN,
    LOGGER,
    OVERKIZ_DEVICE_TO_PLATFORM,
    PLATFORMS,
    UPDATE_INTERVAL_ALL_ASSUMED_STATE,
    UPDATE_INTERVAL_LOCAL,
)
from .coordinator import OverkizDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class HomeAssistantOverkizData:
    """Overkiz data stored in the runtime data object."""

    coordinator: OverkizDataUpdateCoordinator
    platforms: defaultdict[Platform, list[Device]]
    scenarios: list[PersistedActionGroup]


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


async def async_setup_entry(hass: HomeAssistant, entry: OverkizDataConfigEntry) -> bool:
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

    # Rexel Cloud API (OAuth2)
    elif entry.data.get(CONF_HUB) == Server.REXEL:
        client = await create_rexel_client(hass, entry)

    # Somfy multi-account Cloud API (resumable token)
    elif entry.data.get(CONF_HUB) == Server.SOMFY:
        client = await create_somfy_client(hass, entry)

    # Overkiz Cloud API
    else:
        client = create_cloud_client(
            hass,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            server=entry.data[CONF_HUB],
        )

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

    coordinator = OverkizDataUpdateCoordinator(
        hass,
        entry,
        LOGGER,
        client=client,
        devices=setup.devices,
        places=setup.root_place,
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

    platforms: defaultdict[Platform, list[Device]] = defaultdict(list)

    entry.runtime_data = HomeAssistantOverkizData(
        coordinator=coordinator, platforms=platforms, scenarios=scenarios
    )

    # Map Overkiz entities to Home Assistant platform
    for device in coordinator.data.values():
        if platform := OVERKIZ_DEVICE_TO_PLATFORM.get(
            device.widget
        ) or OVERKIZ_DEVICE_TO_PLATFORM.get(device.ui_class):
            platforms[platform].append(device)

    device_registry = dr.async_get(hass)

    for gateway in setup.gateways:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway.id)},
            model=gateway.type.beautify_name if gateway.type else None,
            model_id=str(gateway.type),
            manufacturer=client.server_config.manufacturer,
            name=gateway.type.beautify_name if gateway.type else gateway.id,
            sw_version=gateway.connectivity.protocol_version,
            hw_version=f"{gateway.type}:{gateway.sub_type}"
            if gateway.type and gateway.sub_type
            else None,
            configuration_url=client.server_config.configuration_url,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: OverkizDataConfigEntry
) -> bool:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 2:
        await _async_migrate_strenum_unique_ids(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


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
