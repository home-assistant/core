"""Teslemetry integration."""

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

from aiohttp import ClientError
from aiopowerwall import PowerwallClient, PowerwallEnergySite, PowerwallError
from bleak.exc import BleakError
from tesla_fleet_api.const import Scope
from tesla_fleet_api.exceptions import (
    Forbidden,
    InvalidToken,
    LoginRequired,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.router import VehicleRouter
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry, Vehicle
from teslemetry_stream import TeslemetryStream
from teslemetry_stream.const import SseTopic

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
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
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CLIENT_ID,
    CONF_VIN,
    DOMAIN,
    LOGGER,
    POWERWALL_KEY_FILE,
    RSA_PARENT_KEY,
    SUBENTRY_TYPE_ENERGY_SITE,
    SUBENTRY_TYPE_VEHICLE,
    VEHICLE_ISSUE_LEARN_MORE,
)
from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryMetadataCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .helpers import async_get_ble_parent, async_update_device_sw_version, flatten
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

# Exact SSE topics the integration consumes. An explicit allowlist keeps a
# new server topic from silently adding traffic or data exposure to HA.
STREAM_TOPICS: Final = (
    SseTopic.STATE,
    SseTopic.VEHICLE_DATA,
    SseTopic.DATA,
    SseTopic.CONNECTIVITY,
    SseTopic.CREDITS,
    SseTopic.LIVE_STATUS,
    SseTopic.SITE_INFO,
    SseTopic.TARIFF_CONTENT_V2,
)


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


def _ble_address_for_vin(entry: TeslemetryConfigEntry, vin: str) -> str | None:
    """Return the paired Bluetooth address for a vehicle, if one was added."""
    for subentry in entry.subentries.values():
        if (
            subentry.subentry_type == SUBENTRY_TYPE_VEHICLE
            and subentry.data.get(CONF_VIN) == vin
        ):
            return subentry.data.get(CONF_ADDRESS)
    return None


# Loading the BLE key raises OSError (I/O), ValueError (bad PEM),
# AssertionError (a valid PEM that is not an EC private key), or TypeError
# (an encrypted PEM, which cryptography rejects when no password is given).
_BLE_KEY_ERRORS: Final = (OSError, ValueError, AssertionError, TypeError)


async def _async_resolve_vehicle_api(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    vin: str,
    cloud_vehicle: Vehicle,
) -> Vehicle | VehicleRouter:
    """Return the API a vehicle's platforms should call."""
    address = _ble_address_for_vin(entry, vin)
    if not address:
        return cloud_vehicle

    # A bad BLE key file for one vehicle must not tear down the whole entry.
    try:
        parent = await async_get_ble_parent(hass)
    except _BLE_KEY_ERRORS:
        LOGGER.warning(
            "Failed to load the Bluetooth key for vehicle %s; "
            "falling back to cloud control",
            vin,
            exc_info=True,
        )
        return cloud_vehicle
    # raise_unconfirmed=False avoids re-sending a non-idempotent command to cloud; keepalive_interval=None avoids holding the link open and keeping the car awake.
    bluetooth_vehicle = parent.vehicles.createBluetooth(
        vin,
        confirmation="verify",
        raise_unconfirmed=False,
        keepalive_interval=None,
    )

    @callback
    def _in_range() -> bool:
        """Report whether the vehicle is currently reachable over Bluetooth."""
        device = async_ble_device_from_address(hass, address, connectable=True)
        if device is None:
            return False
        # The library never refreshes the BLE handle, so set it here while it is known fresh.
        bluetooth_vehicle.set_device(device)
        return True

    return VehicleRouter(bluetooth_vehicle, cloud_vehicle, health=_in_range)


def _find_energy_subentry_id(entry: TeslemetryConfigEntry, site_id: int) -> str | None:
    """Return the user-added local-control subentry id bound to site_id, if any."""
    return next(
        (
            subentry.subentry_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ENERGY_SITE
            and subentry.unique_id == str(site_id)
        ),
        None,
    )


def _remove_stale_subentries(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    subentry_type: str,
    current_subentry_ids: set[str],
) -> None:
    """Remove subentries of the given type with no matching product."""
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
    products: list[dict[str, Any]],
) -> None:
    """Remove energy-site subentries whose site is no longer on the account."""
    if Scope.ENERGY_DEVICE_DATA not in scopes:
        return
    # Prune on the raw product list; access:false can be transient, not a removal.
    product_site_ids = {
        str(product["energy_site_id"])
        for product in products
        if "energy_site_id" in product
    }
    _remove_stale_subentries(
        hass,
        entry,
        SUBENTRY_TYPE_ENERGY_SITE,
        {
            subentry.subentry_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ENERGY_SITE
            and subentry.unique_id in product_site_ids
        },
    )


async def _async_get_rsa_key_pem(hass: HomeAssistant) -> bytes:
    """Return the integration's RSA private key PEM, generating it if needed."""
    pem: bytes | None = hass.data.get(RSA_PARENT_KEY)
    if pem is None:
        path = hass.config.path(POWERWALL_KEY_FILE)
        await Teslemetry(
            session=async_get_clientsession(hass), access_token=""
        ).get_rsa_private_key(path)
        pem = await hass.async_add_executor_job(Path(path).read_bytes)
        hass.data[RSA_PARENT_KEY] = pem
    return pem


# aiopowerwall raises PowerwallError; key I/O and parsing raise OSError/ValueError.
_LOCAL_CONTROL_ERRORS: Final = (OSError, ValueError, PowerwallError)


async def _async_resolve_local_control(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    battery: bool,
    site_id: int,
    cloud_energy_site: EnergySite,
) -> tuple[bool, str | None, EnergySite | EnergySiteRouter]:
    """Resolve opt-in local control for an energy site."""
    # Only a battery/Powerwall gateway can pair for local (TEDAPI) control.
    if not battery:
        return False, None, cloud_energy_site
    subentry_id = _find_energy_subentry_id(entry, site_id)
    if subentry_id is None:
        return True, None, cloud_energy_site
    # A local-gateway failure for one site must not tear down the integration.
    try:
        api = await _async_resolve_energy_site_api(
            hass, entry, subentry_id, cloud_energy_site
        )
    except _LOCAL_CONTROL_ERRORS:
        LOGGER.warning(
            "Failed to set up local control for energy site %s; "
            "falling back to cloud control",
            site_id,
            exc_info=True,
        )
        return True, subentry_id, cloud_energy_site
    return True, subentry_id, api


async def _async_resolve_energy_site_api(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    subentry_id: str,
    cloud_energy_site: EnergySite,
) -> EnergySite | EnergySiteRouter:
    """Return the API an energy site's platforms should call."""
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

    implementation = await async_get_config_entry_implementation(hass, entry)
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

    # Create the stream (created lazily for the first eligible vehicle or
    # energy site, so energy-only accounts still open the account stream)
    stream: TeslemetryStream | None = None

    def create_stream() -> TeslemetryStream:
        return TeslemetryStream(
            session,
            access_token,
            server=f"{region.lower()}.teslemetry.com",
            parse_timestamp=True,
            manual=True,
            topics=STREAM_TOPICS,
        )

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
                stream = create_stream()

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

            vehicle_api = await _async_resolve_vehicle_api(
                hass,
                entry,
                vin,
                vehicle,
            )

            vehicles.append(
                TeslemetryVehicleData(
                    api=vehicle_api,
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

            # Create stream if required (for first energy site)
            if not stream:
                stream = create_stream()

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

            (
                live_coordinator,
                info_coordinator,
                history_coordinator,
            ) = await _async_setup_energy_site(
                hass,
                entry,
                stream,
                energy_site,
                product,
                site_id,
                powerwall,
            )

            (
                can_local_control,
                subentry_id,
                energy_site_api,
            ) = await _async_resolve_local_control(
                hass, entry, bool(battery), site_id, energy_site
            )

            energysites.append(
                TeslemetryEnergyData(
                    api=energy_site_api,
                    live_coordinator=live_coordinator,
                    info_coordinator=info_coordinator,
                    history_coordinator=history_coordinator,
                    id=site_id,
                    device=device,
                    can_local_control=can_local_control,
                    subentry_id=subentry_id,
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

    _prune_energy_subentries(hass, entry, scopes, products)

    entry.runtime_data = TeslemetryData(
        vehicles=vehicles,
        energysites=energysites,
        scopes=scopes,
        stream=stream,
        metadata_coordinator=metadata_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _setup_subentry_change_reload(hass, entry)

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
        # The stream is the only freshness signal for the energy coordinators, so
        # a dropped connection must mark their entities unavailable rather than
        # leaving stale live/info/tariff data available indefinitely.
        if energysites:
            entry.async_on_unload(
                stream.async_add_connection_listener(
                    create_handle_energy_stream_connection(energysites)
                )
            )
        entry.async_create_background_task(hass, stream.listen(), "Teslemetry Stream")

    return True


def _setup_subentry_change_reload(
    hass: HomeAssistant, entry: TeslemetryConfigEntry
) -> None:
    """Reload the entry when a subentry is added or removed."""
    known = set(entry.subentries)

    async def _handle_update(
        hass: HomeAssistant, updated_entry: TeslemetryConfigEntry
    ) -> None:
        nonlocal known
        current = set(updated_entry.subentries)
        if known.symmetric_difference(current):
            hass.config_entries.async_schedule_reload(updated_entry.entry_id)
        # Refresh known so a later update does not re-fire on this same change.
        known = current

    entry.async_on_unload(entry.add_update_listener(_handle_update))


def create_handle_energy_stream_connection(
    energysites: list[TeslemetryEnergyData],
) -> Callable[[bool], None]:
    """Create a stream connection listener for the energy coordinators."""

    @callback
    def handle_connection(connected: bool) -> None:
        """Fail stream-driven energy coordinators while the stream is down.

        Each subsequent streamed document restores its coordinator via
        async_set_updated_data, so no reload is required on reconnect.
        """
        if connected:
            return
        error = UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="stream_disconnected",
        )
        for energysite in energysites:
            if energysite.live_coordinator is not None:
                energysite.live_coordinator.async_set_update_error(error)
            energysite.info_coordinator.async_set_update_error(error)

    return handle_connection


async def _async_setup_energy_site(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    stream: TeslemetryStream,
    energy_site: EnergySite,
    product: dict[str, Any],
    site_id: int,
    powerwall: Any,
) -> tuple[
    TeslemetryEnergySiteLiveCoordinator | None,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergyHistoryCoordinator | None,
]:
    """Cold-read live status, build the energy coordinators, and register listeners."""
    # The stream has no ready boundary, so keep a deterministic REST cold read
    # for setup auth/error handling before switching to listener-driven updates.
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

    live_coordinator = (
        TeslemetryEnergySiteLiveCoordinator(hass, entry, energy_site, live_status)
        if isinstance(live_status, dict)
        else None
    )
    info_coordinator = TeslemetryEnergySiteInfoCoordinator(
        hass, entry, energy_site, product
    )

    # Register before stream.listen() so the opening snapshot cannot be missed.
    stream_energysite = stream.get_energysite(site_id)
    if live_coordinator is not None:
        entry.async_on_unload(
            stream_energysite.listen_LiveStatus(live_coordinator.handle_stream_update)
        )
    entry.async_on_unload(
        stream_energysite.listen_SiteInfo(info_coordinator.handle_site_info)
    )
    entry.async_on_unload(
        stream_energysite.listen_TariffContentV2(
            info_coordinator.handle_tariff_content_v2
        )
    )

    history_coordinator = (
        TeslemetryEnergyHistoryCoordinator(hass, entry, energy_site)
        if powerwall
        else None
    )

    return live_coordinator, info_coordinator, history_coordinator


async def async_unload_entry(hass: HomeAssistant, entry: TeslemetryConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Release any on-demand Bluetooth link only after platforms unloaded, or the still-loaded entry's backends must keep working.
        for vehicle in entry.runtime_data.vehicles:
            if isinstance(vehicle.api, VehicleRouter):
                try:
                    await vehicle.api.primary.disconnect()
                except (BleakError, TeslaFleetError, TimeoutError) as err:
                    LOGGER.debug(
                        "Error disconnecting Bluetooth for %s: %s", vehicle.vin, err
                    )
    return unloaded


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
                hass, energysite.id, entry.entry_id, energysite.info_coordinator
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
            create_vehicle_streaming_listener(hass, vehicle.vin, entry.entry_id)
        )
    )


def create_vehicle_streaming_listener(
    hass: HomeAssistant, vin: str, config_entry_id: str
) -> Callable[[str | None], None]:
    """Create a listener for vehicle streaming version updates."""

    def handle_version(value: str | None) -> None:
        """Handle version update from stream."""
        if value is not None:
            # Remove build from version (e.g., "2024.44.25 abc123" -> "2024.44.25")
            sw_version = value.split(" ")[0]
            async_update_device_sw_version(hass, vin, config_entry_id, sw_version)

    return handle_version


def create_energy_info_listener(
    hass: HomeAssistant,
    site_id: int,
    config_entry_id: str,
    coordinator: TeslemetryEnergySiteInfoCoordinator,
) -> Callable[[], None]:
    """Create a listener for energy site info coordinator updates."""

    def handle_update() -> None:
        """Handle coordinator update."""
        if version := coordinator.data.get("version"):
            async_update_device_sw_version(hass, str(site_id), config_entry_id, version)

    return handle_update
