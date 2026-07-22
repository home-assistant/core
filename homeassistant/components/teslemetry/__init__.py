"""Teslemetry integration."""

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from aiohttp import ClientError
from aiopowerwall import PowerwallClient, PowerwallEnergySite
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    Forbidden,
    InvalidToken,
    LoginRequired,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry
from teslemetry_stream import TeslemetryStream

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CLIENT_ID,
    CONF_SITE_ID,
    DOMAIN,
    LOGGER,
    POWERWALL_KEY_FILE,
    RSA_PARENT_KEY,
    SUBENTRY_TYPE_ENERGY_SITE,
    VEHICLE_ISSUE_LEARN_MORE,
)
from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryMetadataCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .helpers import async_update_device_sw_version, flatten
from .models import TeslemetryData, TeslemetryEnergyData, TeslemetryVehicleData
from .services import async_setup_services

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
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
    setup_in_progress = (
        oauth_session.config_entry.state is ConfigEntryState.SETUP_IN_PROGRESS
    )
    try:
        await oauth_session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        if setup_in_progress:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        # Not in setup: let the coordinator's own OAuth2TokenRequestError
        # handling stop polling and (re)start reauth without tearing
        # down the already-loaded entry.
        oauth_session.config_entry.async_start_reauth(oauth_session.hass)
        raise
    except OAuth2TokenRequestError as err:
        # Recoverable (e.g. 429/5xx). During setup this backs off via the
        # normal ConfigEntryNotReady retry; once loaded, let it propagate so
        # the coordinator treats it as a transient failed update instead.
        if setup_in_progress:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="not_ready_connection_error",
            ) from err
        raise
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
    return cast(str, oauth_session.token[CONF_ACCESS_TOKEN])


def _get_subscribed_ids_from_metadata(
    data: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """Return metadata device IDs that have an active subscription."""
    subscribed_vins = {
        vin for vin, info in data["vehicles"].items() if info.get("access")
    }
    subscribed_site_ids = {
        site_id for site_id, info in data["energy_sites"].items() if info.get("access")
    }

    return subscribed_vins, subscribed_site_ids


def _setup_dynamic_discovery(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    metadata_coordinator: TeslemetryMetadataCoordinator,
    known_vins: set[str],
    known_site_ids: set[str],
) -> None:
    """Set up dynamic device discovery via reload when subscriptions change."""

    @callback
    def _handle_metadata_update() -> None:
        """Handle metadata coordinator update - detect subscription changes."""
        data = metadata_coordinator.data
        if not data:
            return

        current_vins, current_site_ids = _get_subscribed_ids_from_metadata(data)

        added_vins = current_vins - known_vins
        removed_vins = known_vins - current_vins
        added_sites = current_site_ids - known_site_ids
        removed_sites = known_site_ids - current_site_ids

        if added_vins or removed_vins or added_sites or removed_sites:
            LOGGER.info(
                "Tesla subscription changes detected "
                "(added vehicles: %s, removed vehicles: %s, "
                "added energy sites: %s, removed energy sites: %s), "
                "reloading integration",
                added_vins or "none",
                removed_vins or "none",
                added_sites or "none",
                removed_sites or "none",
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        metadata_coordinator.async_add_listener(_handle_metadata_update)
    )


def _async_update_vehicle_repairs(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    vins: set[str],
    vehicle_metadata: dict[str, Any],
) -> None:
    """Create or remove repair issues based on each vehicle's metadata issue."""
    for vin in vins | set(vehicle_metadata):
        info = vehicle_metadata.get(vin, {})
        issue = info.get("issue")
        for issue_type, learn_more_url in VEHICLE_ISSUE_LEARN_MORE.items():
            issue_id = f"{issue_type}_{vin}"
            if vin in vins and info.get("access") and issue == issue_type:
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=issue_type,
                    translation_placeholders={"vehicle": info.get("name") or vin},
                    learn_more_url=learn_more_url,
                    data={
                        "entry_id": entry.entry_id,
                        "vin": vin,
                        "issue_type": issue_type,
                        "vehicle": info.get("name") or vin,
                    },
                )
            else:
                ir.async_delete_issue(hass, DOMAIN, issue_id)


def _setup_vehicle_repairs(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    metadata_coordinator: TeslemetryMetadataCoordinator,
    vins: set[str],
    vehicle_metadata: dict[str, Any],
) -> None:
    """Track vehicle metadata issues and keep repair issues in sync."""

    _async_update_vehicle_repairs(hass, entry, vins, vehicle_metadata)

    @callback
    def _handle_metadata_update() -> None:
        """Re-evaluate vehicle repair issues when metadata changes."""
        data = metadata_coordinator.data
        if not data:
            return
        _async_update_vehicle_repairs(hass, entry, vins, data["vehicles"])

    entry.async_on_unload(
        metadata_coordinator.async_add_listener(_handle_metadata_update)
    )


def _ensure_subentry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    subentry_type: str,
    unique_id: str,
    title: str,
    data: dict[str, Any],
) -> str:
    """Return the subentry id for unique_id, creating or updating it as needed."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == subentry_type and subentry.unique_id == unique_id:
            # Merge over the existing data so keys added by a pairing flow (the
            # energy gateway host/password) are preserved across reloads.
            merged = {**subentry.data, **data}
            if subentry.title != title or dict(subentry.data) != merged:
                hass.config_entries.async_update_subentry(
                    entry, subentry, title=title, data=merged
                )
            return subentry.subentry_id

    subentry = ConfigSubentry(
        data=MappingProxyType(data),
        subentry_type=subentry_type,
        title=title,
        unique_id=unique_id,
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    return subentry.subentry_id


def _remove_stale_subentries(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    subentry_type: str,
    current_subentry_ids: set[str],
) -> None:
    """Remove subentries of the given type with no matching product.

    Filtered by subentry_type so this only prunes its own kind and never
    touches subentries owned by another feature (e.g. vehicle subentries).
    """
    for subentry in list(entry.subentries.values()):
        if (
            subentry.subentry_type == subentry_type
            and subentry.subentry_id not in current_subentry_ids
        ):
            LOGGER.debug("Removing stale subentry %s", subentry.subentry_id)
            hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)


def _prune_energy_subentries(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    scopes: list[Scope],
    energysites: list[TeslemetryEnergyData],
) -> None:
    """Remove energy-site subentries whose site is no longer present.

    Skipped without the energy scope: setup then skips every energy product, so
    an empty site list means the inventory was never resolved rather than that
    the sites are gone. Pruning against it would delete the local gateway
    credentials a user paired.
    """
    if Scope.ENERGY_DEVICE_DATA not in scopes:
        return
    _remove_stale_subentries(
        hass,
        entry,
        SUBENTRY_TYPE_ENERGY_SITE,
        {
            energysite.subentry_id
            for energysite in energysites
            if energysite.subentry_id is not None
        },
    )


async def _async_get_rsa_key_pem(hass: HomeAssistant) -> bytes:
    """Return the integration's RSA private key PEM, generating it if needed.

    Cached on ``hass.data`` so the key file is only touched once even when
    several energy sites are paired for local TEDAPI v1r access.
    """
    pem: bytes | None = hass.data.get(RSA_PARENT_KEY)
    if pem is None:
        path = hass.config.path(POWERWALL_KEY_FILE)
        await Teslemetry(
            session=async_get_clientsession(hass), access_token=""
        ).get_rsa_private_key(path)
        pem = await hass.async_add_executor_job(Path(path).read_bytes)
        hass.data[RSA_PARENT_KEY] = pem
    return pem


async def _async_resolve_energy_site_api(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    subentry_id: str,
    cloud_energy_site: EnergySite,
) -> EnergySite | EnergySiteRouter:
    """Return the API an energy site's platforms should call.

    When the subentry has been paired (its data carries a local gateway
    ``host``/``password``), wrap the cloud EnergySite in an EnergySiteRouter that
    tries the local Powerwall (via aiopowerwall) first and fails over to cloud
    per command. Otherwise returns the plain cloud EnergySite unchanged.
    """
    data = entry.subentries[subentry_id].data
    host = data.get(CONF_HOST)
    password = data.get(CONF_PASSWORD)
    if not host or not password:
        return cloud_energy_site

    key_pem = await _async_get_rsa_key_pem(hass)
    powerwall_client = PowerwallClient(
        host=host,
        gateway_password=password,
        rsa_private_key_pem=key_pem,
        session=async_get_clientsession(hass),
    )
    local_energy_site = PowerwallEnergySite(powerwall_client)
    return EnergySiteRouter(local_energy_site, cloud_energy_site)


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
    # Fetch metadata through the coordinator so it owns the data the platforms
    # read at setup (e.g. per-vehicle config for seat heaters).
    metadata_coordinator = TeslemetryMetadataCoordinator(hass, entry, teslemetry)
    try:
        products_call, _ = await asyncio.gather(
            teslemetry.products(),
            metadata_coordinator.async_config_entry_first_refresh(),
        )
    except InvalidToken as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed_invalid_token",
        ) from e
    except LoginRequired as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed_login_required",
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

    metadata = metadata_coordinator.data
    scopes = metadata["scopes"]
    region = metadata["region"]
    vehicle_metadata = metadata["vehicles"]
    energy_site_metadata = metadata["energy_sites"]
    products = products_call["response"]

    device_registry = dr.async_get(hass)

    # Create array of classes
    vehicles: list[TeslemetryVehicleData] = []
    energysites: list[TeslemetryEnergyData] = []

    # Create the stream (created lazily when first vehicle is found)
    stream: TeslemetryStream | None = None

    # Remember each device identifier we create
    current_devices: set[tuple[str, str]] = set()

    # Track known devices for dynamic discovery (based on metadata access state)
    known_vins, known_site_ids = _get_subscribed_ids_from_metadata(metadata)

    for product in products:
        if (
            "vin" in product
            and vehicle_metadata.get(product["vin"], {}).get("access")
            and Scope.VEHICLE_DEVICE_DATA in scopes
        ):
            vin = product["vin"]
            current_devices.add((DOMAIN, vin))

            # Create stream if required (for first vehicle)
            if not stream:
                stream = TeslemetryStream(
                    session,
                    access_token,
                    server=f"{region.lower()}.teslemetry.com",
                    parse_timestamp=True,
                    manual=True,
                )

            # Remove the protobuff 'cached_data' that we do not use to save memory
            product.pop("cached_data", None)
            vehicle = teslemetry.vehicles.create(vin)
            coordinator = TeslemetryVehicleDataCoordinator(
                hass, entry, vehicle, product
            )
            firmware = vehicle_metadata[vin].get("firmware")
            device = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                manufacturer="Tesla",
                configuration_url=f"https://teslemetry.com/console/vehicle/{vin}",
                name=product["display_name"],
                model=vehicle.model,
                model_id=vin[3],
                serial_number=vin,
                sw_version=firmware,
            )

            poll = vehicle_metadata[vin].get("polling", False)

            entry.async_on_unload(
                stream.async_add_listener(
                    create_handle_vehicle_stream(vin, coordinator),
                    {"vin": vin},
                )
            )
            stream_vehicle = stream.get_vehicle(vin)

            vehicles.append(
                TeslemetryVehicleData(
                    api=vehicle,
                    config_entry=entry,
                    coordinator=coordinator,
                    poll=poll,
                    stream=stream,
                    stream_vehicle=stream_vehicle,
                    vin=vin,
                    firmware=firmware or "Unknown",
                    device=device,
                )
            )

        elif (
            "energy_site_id" in product
            and Scope.ENERGY_DEVICE_DATA in scopes
            and energy_site_metadata.get(str(product["energy_site_id"]), {}).get(
                "access"
            )
        ):
            site_id = product["energy_site_id"]

            battery = product["components"]["battery"]
            powerwall = battery or product["components"]["solar"]
            wall_connector = "wall_connectors" in product["components"]
            if not powerwall and not wall_connector:
                LOGGER.debug(
                    "Skipping Energy Site %s as it has no components",
                    site_id,
                )
                continue

            current_devices.add((DOMAIN, str(site_id)))
            if wall_connector:
                current_devices |= {
                    (DOMAIN, c["din"]) for c in product["components"]["wall_connectors"]
                }

            energy_site = teslemetry.energySites.create(site_id)
            device = DeviceInfo(
                identifiers={(DOMAIN, str(site_id))},
                manufacturer="Tesla",
                configuration_url=f"https://teslemetry.com/console/energy/{site_id}",
                name=product.get("site_name", "Energy Site"),
                serial_number=str(site_id),
            )

            # For initial setup, raise auth errors properly
            try:
                live_status = (await energy_site.live_status())["response"]
            except InvalidToken as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed_invalid_token",
                ) from e
            except LoginRequired as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed_login_required",
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

            # Only a battery/Powerwall gateway can pair for local (TEDAPI)
            # command control; solar-only and wall-connector-only sites get no
            # local-control subentry or routing.
            subentry_id: str | None = None
            energy_site_api: EnergySite | EnergySiteRouter = energy_site
            if battery:
                subentry_id = _ensure_subentry(
                    hass,
                    entry,
                    SUBENTRY_TYPE_ENERGY_SITE,
                    str(site_id),
                    product.get("site_name", "Energy Site"),
                    {CONF_SITE_ID: site_id},
                )
                energy_site_api = await _async_resolve_energy_site_api(
                    hass, entry, subentry_id, energy_site
                )

            energysites.append(
                TeslemetryEnergyData(
                    api=energy_site_api,
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
                    subentry_id=subentry_id,
                    gateway_id=product.get("gateway_id"),
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
            device_registry.async_remove_device(device_entry.id)

    _prune_energy_subentries(hass, entry, scopes, energysites)

    entry.runtime_data = TeslemetryData(
        vehicles=vehicles,
        energysites=energysites,
        scopes=scopes,
        stream=stream,
        metadata_coordinator=metadata_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _setup_dynamic_discovery(
        hass,
        entry,
        metadata_coordinator,
        known_vins,
        known_site_ids,
    )

    _setup_vehicle_repairs(
        hass,
        entry,
        metadata_coordinator,
        {vehicle.vin for vehicle in vehicles},
        vehicle_metadata,
    )

    if stream:
        entry.async_on_unload(stream.close)
        entry.async_create_background_task(hass, stream.listen(), "Teslemetry Stream")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TeslemetryConfigEntry
) -> bool:
    """Migrate config entry."""

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


def create_handle_vehicle_stream(
    vin: str, coordinator: TeslemetryVehicleDataCoordinator
) -> Callable[[dict[str, Any]], None]:
    """Create a handle vehicle stream function."""

    def handle_vehicle_stream(data: dict[str, Any]) -> None:
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
        if (part_name := component.get("part_name")) and part_name != "Unknown":
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
) -> None:
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
