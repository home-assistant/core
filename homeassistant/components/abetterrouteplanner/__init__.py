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

    websession = async_get_clientsession(hass)
    auth = AbetterrouteplannerAuth(session)
    client = AbrpClient(websession, ABRP_APP_KEY, auth)

    vehicles = await async_fetch_garage(client)

    # Create devices before forwarding platforms so silent vehicles get a card.
    device_registry = dr.async_get(hass)
    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
    for raw, display in vehicles:
        if raw.vehicle_id not in selected_ids:
            continue
        scope = f"{entry.unique_id}_{raw.vehicle_id}"
        if display is None:
            # INFO, not DEBUG: a catalog miss should be greppable by default.
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
            model=display.model_name if display is not None else raw.vehicle_model,
            name=raw.name or raw.vehicle_model,
            configuration_url=(
                f"https://abetterrouteplanner.com/?vehicle_id={raw.vehicle_id}"
            ),
        )

    telemetry_coordinator = AbrpTelemetryCoordinator(hass, entry)

    # The v2 endpoint rejects an unknown id as a whole-subscription failure.
    present_ids = {raw.vehicle_id for raw, _ in vehicles}
    vehicle_ids = [
        int(vehicle_id)
        for vehicle_id in entry.data[CONF_VEHICLE_IDS]
        if int(vehicle_id) in present_ids
    ]

    # Seed before starting the stream so the snapshot is the merge baseline.
    stream: TelemetryStream | None = None
    if vehicle_ids:
        # Known vehicles restore via the registry probe + ``RestoreSensor``.
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
