"""Teslemetry integration."""

import asyncio
from collections.abc import Callable
from functools import partial
from typing import Final

from aiohttp import ClientError, ClientResponseError
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    Forbidden,
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry import Teslemetry
from teslemetry_stream import TeslemetryStream

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import CLIENT_ID, DOMAIN, LOGGER
from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .helpers import async_update_device_sw_version, flatten
from .models import TeslemetryData, TeslemetryEnergyData, TeslemetryVehicleData
from .services import async_setup_services

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

type TeslemetryConfigEntry = ConfigEntry[TeslemetryData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telemetry integration."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, "", name="Teslemetry"),
    )
    async_setup_services(hass)
    return True


async def _get_access_token(oauth_session: OAuth2Session) -> str:
    """Get a valid access token, refreshing if necessary."""
    LOGGER.debug(
        "Token valid: %s, expires_at: %s",
        oauth_session.valid_token,
        oauth_session.token.get("expires_at"),
    )
    try:
        await oauth_session.async_ensure_token_valid()
    except ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_ready_connection_error",
        ) from err
    except (KeyError, TypeError) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="token_data_malformed",
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_ready_connection_error",
        ) from err
    return oauth_session.token[CONF_ACCESS_TOKEN]


async def async_setup_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Set up Teslemetry config."""

    if "token" not in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="token_data_malformed",
        )

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="oauth_implementation_not_available",
        ) from err
    oauth_session = OAuth2Session(hass, entry, implementation)

    session = async_get_clientsession(hass)

    # Create API connection
    access_token = partial(_get_access_token, oauth_session)
    teslemetry = Teslemetry(
        session=session,
        access_token=access_token,
    )
    try:
        calls = await asyncio.gather(
            teslemetry.metadata(),
            teslemetry.products(),
        )
    except InvalidToken as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed_invalid_token",
        ) from e
    except SubscriptionRequired as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed_subscription_required",
        ) from e
    except TeslaFleetError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_ready_api_error",
        ) from e

    scopes = calls[0]["scopes"]
    region = calls[0]["region"]
    vehicle_metadata = calls[0]["vehicles"]
    products = calls[1]["response"]

    device_registry = dr.async_get(hass)

    # Create array of classes
    vehicles: list[TeslemetryVehicleData] = []
    energysites: list[TeslemetryEnergyData] = []

    # Create the stream
    stream: TeslemetryStream | None = None

    # Remember each device identifier we create
    current_devices: set[tuple[str, str]] = set()

    for product in products:
        if (
            "vin" in product
            and vehicle_metadata.get(product["vin"], {}).get("access")
            and Scope.VEHICLE_DEVICE_DATA in scopes
        ):
            # Remove the protobuff 'cached_data' that we do not use to save memory
            product.pop("cached_data", None)
            vin = product["vin"]
            vehicle = teslemetry.vehicles.create(vin)
            coordinator = TeslemetryVehicleDataCoordinator(
                hass, entry, vehicle, product
            )
            firmware = vehicle_metadata[vin].get("firmware")
            device = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                manufacturer="Tesla",
                configuration_url="https://teslemetry.com/console",
                name=product["display_name"],
                model=vehicle.model,
                model_id=vin[3],
                serial_number=vin,
                sw_version=firmware,
            )
            current_devices.add((DOMAIN, vin))

            # Create stream if required
            if not stream:
                stream = TeslemetryStream(
                    session,
                    access_token,
                    server=f"{region.lower()}.teslemetry.com",
                    parse_timestamp=True,
                    manual=True,
                )

            remove_listener = stream.async_add_listener(
                create_handle_vehicle_stream(vin, coordinator),
                {"vin": vin},
            )
            stream_vehicle = stream.get_vehicle(vin)
            poll = vehicle_metadata[vin].get("polling", False)

            vehicles.append(
                TeslemetryVehicleData(
                    api=vehicle,
                    config_entry=entry,
                    coordinator=coordinator,
                    poll=poll,
                    stream=stream,
                    stream_vehicle=stream_vehicle,
                    vin=vin,
                    firmware=firmware,
                    device=device,
                    remove_listener=remove_listener,
                )
            )

        elif "energy_site_id" in product and Scope.ENERGY_DEVICE_DATA in scopes:
            site_id = product["energy_site_id"]
            powerwall = (
                product["components"]["battery"] or product["components"]["solar"]
            )
            wall_connector = "wall_connectors" in product["components"]
            if not powerwall and not wall_connector:
                LOGGER.debug(
                    "Skipping Energy Site %s as it has no components",
                    site_id,
                )
                continue

            energy_site = teslemetry.energySites.create(site_id)
            device = DeviceInfo(
                identifiers={(DOMAIN, str(site_id))},
                manufacturer="Tesla",
                configuration_url="https://teslemetry.com/console",
                name=product.get("site_name", "Energy Site"),
                serial_number=str(site_id),
            )
            current_devices.add((DOMAIN, str(site_id)))

            if wall_connector:
                for connector in product["components"]["wall_connectors"]:
                    current_devices.add((DOMAIN, connector["din"]))

            # Check live status endpoint works before creating its coordinator
            try:
                live_status = (await energy_site.live_status())["response"]
            except InvalidToken as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed_invalid_token",
                ) from e
            except SubscriptionRequired as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed_subscription_required",
                ) from e
            except Forbidden as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed_invalid_token",
                ) from e
            except TeslaFleetError as e:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="not_ready_api_error",
                ) from e

            energysites.append(
                TeslemetryEnergyData(
                    api=energy_site,
                    live_coordinator=(
                        TeslemetryEnergySiteLiveCoordinator(
                            hass, entry, energy_site, live_status
                        )
                        if isinstance(live_status, dict)
                        else None
                    ),
                    info_coordinator=TeslemetryEnergySiteInfoCoordinator(
                        hass, entry, energy_site, product
                    ),
                    history_coordinator=(
                        TeslemetryEnergyHistoryCoordinator(hass, entry, energy_site)
                        if powerwall
                        else None
                    ),
                    id=site_id,
                    device=device,
                )
            )

    # Run all first refreshes
    await asyncio.gather(
        *(async_setup_stream(hass, entry, vehicle) for vehicle in vehicles),
        *(
            vehicle.coordinator.async_config_entry_first_refresh()
            for vehicle in vehicles
            if vehicle.poll
        ),
        *(
            energysite.info_coordinator.async_config_entry_first_refresh()
            for energysite in energysites
        ),
    )

    # Register listeners for polling vehicle sw_version updates
    for vehicle_data in vehicles:
        if vehicle_data.poll:
            entry.async_on_unload(
                vehicle_data.coordinator.async_add_listener(
                    create_vehicle_polling_listener(
                        hass, vehicle_data.vin, vehicle_data.coordinator
                    )
                )
            )

    # Setup energy devices with models, versions, and listeners
    for energysite in energysites:
        async_setup_energy_device(hass, entry, energysite, device_registry)

    # Remove devices that are no longer present
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not any(
            identifier in current_devices for identifier in device_entry.identifiers
        ):
            LOGGER.debug("Removing stale device %s", device_entry.id)
            device_registry.async_update_device(
                device_id=device_entry.id,
                remove_config_entry_id=entry.entry_id,
            )

    # Setup Platforms
    entry.runtime_data = TeslemetryData(vehicles, energysites, scopes, stream)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if stream:
        entry.async_create_background_task(hass, stream.listen(), "Teslemetry Stream")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TeslemetryConfigEntry
) -> bool:
    """Migrate config entry."""
    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        access_token = config_entry.data[CONF_ACCESS_TOKEN]
        session = async_get_clientsession(hass)

        # Convert legacy access token to OAuth tokens using migrate endpoint
        try:
            data = await Teslemetry(session, access_token).migrate_to_oauth(
                CLIENT_ID, hass.config.location_name
            )
        except (ClientError, TypeError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed_migration",
            ) from e

        # Add auth_implementation for OAuth2 flow compatibility
        data["auth_implementation"] = DOMAIN

        return hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            version=2,
        )
    return True


def create_handle_vehicle_stream(vin: str, coordinator) -> Callable[[dict], None]:
    """Create a handle vehicle stream function."""

    def handle_vehicle_stream(data: dict) -> None:
        """Handle vehicle data from the stream."""
        if "vehicle_data" in data:
            LOGGER.debug("Streaming received vehicle data from %s", vin)
            coordinator.async_set_updated_data(flatten(data["vehicle_data"]))
        elif "state" in data:
            LOGGER.debug("Streaming received state from %s", vin)
            coordinator.data["state"] = data["state"]
            coordinator.async_set_updated_data(coordinator.data)

    return handle_vehicle_stream


def async_setup_energy_device(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    energysite: TeslemetryEnergyData,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Set up energy device with models, versions, and listeners."""
    data = energysite.info_coordinator.data
    models = set()
    for component in (
        *data.get("components_gateways", []),
        *data.get("components_batteries", []),
    ):
        if part_name := component.get("part_name"):
            models.add(part_name)
    if models:
        energysite.device["model"] = ", ".join(sorted(models))

    if version := data.get("version"):
        energysite.device["sw_version"] = version

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, **energysite.device
    )

    entry.async_on_unload(
        energysite.info_coordinator.async_add_listener(
            create_energy_info_listener(
                hass, energysite.id, energysite.info_coordinator
            )
        )
    )


async def async_setup_stream(
    hass: HomeAssistant, entry: TeslemetryConfigEntry, vehicle: TeslemetryVehicleData
):
    """Set up the stream for a vehicle."""

    await vehicle.stream_vehicle.get_config()
    entry.async_create_background_task(
        hass,
        vehicle.stream_vehicle.prefer_typed(True),
        f"Prefer typed for {vehicle.vin}",
    )

    entry.async_on_unload(
        vehicle.stream_vehicle.listen_Version(
            create_vehicle_streaming_listener(hass, vehicle.vin)
        )
    )


def create_vehicle_streaming_listener(
    hass: HomeAssistant, vin: str
) -> Callable[[str | None], None]:
    """Create a listener for vehicle streaming version updates."""

    def handle_version(value: str | None) -> None:
        """Handle version update from stream."""
        if value is not None:
            # Remove build from version (e.g., "2024.44.25 abc123" -> "2024.44.25")
            sw_version = value.split(" ")[0]
            async_update_device_sw_version(hass, vin, sw_version)

    return handle_version


def create_vehicle_polling_listener(
    hass: HomeAssistant, vin: str, coordinator: TeslemetryVehicleDataCoordinator
) -> Callable[[], None]:
    """Create a listener for vehicle polling coordinator updates."""

    def handle_update() -> None:
        """Handle coordinator update."""
        if version := coordinator.data.get("vehicle_state_car_version"):
            # Remove build from version (e.g., "2024.44.25 abc123" -> "2024.44.25")
            sw_version = version.split(" ")[0]
            async_update_device_sw_version(hass, vin, sw_version)

    return handle_update


def create_energy_info_listener(
    hass: HomeAssistant,
    site_id: int,
    coordinator: TeslemetryEnergySiteInfoCoordinator,
) -> Callable[[], None]:
    """Create a listener for energy site info coordinator updates."""

    def handle_update() -> None:
        """Handle coordinator update."""
        if version := coordinator.data.get("version"):
            async_update_device_sw_version(hass, str(site_id), version)

    return handle_update
