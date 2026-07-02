"""The A Better Routeplanner integration."""

from http import HTTPStatus
import logging

from aioabrp import AbrpClient, TelemetryStream
from aiohttp import ClientError, ClientResponseError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .auth import AbetterrouteplannerAuth
from .const import ABRP_APP_KEY, CONF_VEHICLE_IDS, DOMAIN
from .coordinator import (
    AbetterrouteplannerConfigEntry,
    AbrpData,
    AbrpTelemetryCoordinator,
    async_fetch_garage,
)
from .oauth import AbetterrouteplannerOAuth2Implementation
from .sensor import vehicles_without_sensors

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the A Better Routeplanner component."""
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, AbetterrouteplannerOAuth2Implementation(hass)
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AbetterrouteplannerConfigEntry
) -> bool:
    """Set up A Better Routeplanner from a config entry."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except config_entry_oauth2_flow.ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="oauth2_session_not_valid",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_token_refresh_failed",
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_token_refresh_failed",
        ) from err

    # Build the auth wrapper + client + websession once; they back the
    # one-shot garage fetch, the seed poll, and the SSE consumer below. The
    # stream is owned by the config entry and stopped on unload.
    websession = async_get_clientsession(hass)
    auth = AbetterrouteplannerAuth(session)
    client = AbrpClient(websession, ABRP_APP_KEY, auth)

    # One-shot garage fetch: vehicle identity joined with its device-card
    # display. Raises ConfigEntryAuthFailed / ConfigEntryNotReady on failure.
    vehicles = await async_fetch_garage(client)

    # Anchor a device per selected vehicle BEFORE forwarding the platforms so
    # the device card is present immediately after setup — even for a vehicle
    # that's silent on SSE. The composed model/manufacturer mirror what the
    # telemetry entities would produce. The card reflects the garage as of this
    # setup/reload; live rename / late-display recovery is a follow-up.
    device_registry = dr.async_get(hass)
    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
    for raw, display in vehicles:
        if raw.vehicle_id not in selected_ids:
            continue
        scope = f"{entry.unique_id}_{raw.vehicle_id}"
        if display is None:
            # Surface why a selected vehicle's card shows the raw typecode (a
            # catalog miss) so it is greppable without enabling DEBUG; one line
            # per degraded vehicle at setup only, no per-poll spam.
            _LOGGER.info(
                "No display metadata for vehicle %d (typecode %s); device card "
                "shows the raw typecode until the entry is reloaded",
                raw.vehicle_id,
                raw.vehicle_model,
            )
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, scope)},
            manufacturer=display.manufacturer if display is not None else None,
            model=display.display_name if display is not None else raw.vehicle_model,
            name=raw.name or raw.vehicle_model,
            configuration_url=(
                f"https://abetterrouteplanner.com/?vehicle_id={raw.vehicle_id}"
            ),
        )

    telemetry_coordinator = AbrpTelemetryCoordinator(hass, entry)

    # Filter the selection against the garage snapshot so we only stream for
    # vehicles the API actually knows about; the v2 endpoint rejects an unknown
    # id as a whole-subscription failure, and an entry with no live selections
    # (e.g. user removed every vehicle in ABRP) should idle until a reload
    # re-discovers them.
    present_ids = {raw.vehicle_id for raw, _ in vehicles}
    vehicle_ids = [
        int(vehicle_id)
        for vehicle_id in entry.data[CONF_VEHICLE_IDS]
        if int(vehicle_id) in present_ids
    ]

    # Seed the telemetry coordinator BEFORE starting the stream so the cached
    # snapshot is the baseline the stream merges into. Metrics that only arrive
    # later (null in the seed, non-null on a later SSE frame) are created via the
    # ``signal_new_metric`` dispatcher path, so setup need not wait for them.
    stream: TelemetryStream | None = None
    if vehicle_ids:
        # Poll one-shot only for vehicles we have never created sensors for
        # (fresh install or a newly-added vehicle). Vehicles already known to
        # the entity registry restore their last values via the sensor
        # platform's eager-from-registry probe + ``RestoreSensor``, so
        # re-polling them on every startup is wasted work.
        new_vehicles = vehicles_without_sensors(hass, entry, vehicle_ids)
        if new_vehicles:
            await telemetry_coordinator.async_seed(client, new_vehicles)
        stream = TelemetryStream(
            websession,
            ABRP_APP_KEY,
            auth,
            vehicle_ids,
            on_update=telemetry_coordinator.on_update,
            on_connection_change=telemetry_coordinator.on_connection_change,
            name=entry.title,
        )
        await stream.start()

    entry.runtime_data = AbrpData(
        session=session,
        vehicles=vehicles,
        telemetry_coordinator=telemetry_coordinator,
        stream=stream,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AbetterrouteplannerConfigEntry
) -> bool:
    """Unload a config entry."""
    if (stream := entry.runtime_data.stream) is not None:
        await stream.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: AbetterrouteplannerConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting a device only once its vehicle is no longer active.

    Refused while the vehicle is still in the ``selected ∩ present`` set, where
    ``present`` is the garage snapshot taken at the last setup/reload; allowed
    once it drops out of either (deselected in the config entry, or absent from
    that snapshot), so an orphaned device card can be cleaned up. A vehicle
    removed from ABRP after setup stays refused until the entry is reloaded.
    """
    selected_ids = {
        int(vehicle_id) for vehicle_id in config_entry.data[CONF_VEHICLE_IDS]
    }
    active_scopes = {
        f"{config_entry.unique_id}_{raw.vehicle_id}"
        for raw, _ in config_entry.runtime_data.vehicles
        if raw.vehicle_id in selected_ids
    }
    return not any(
        identifier[0] == DOMAIN and identifier[1] in active_scopes
        for identifier in device_entry.identifiers
    )
