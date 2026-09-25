"""The A Better Routeplanner integration."""

import logging

from aioabrp import AbrpClient, TelemetryStream
from aiohttp import ClientError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .auth import AbetterrouteplannerAuth
from .const import ABRP_APP_KEY, DOMAIN
from .coordinator import (
    AbetterrouteplannerConfigEntry,
    AbrpData,
    AbrpTelemetryCoordinator,
    async_fetch_garage,
)
from .oauth import AbetterrouteplannerOAuth2Implementation

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
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="oauth2_session_not_valid",
        ) from err
    except (OAuth2TokenRequestError, ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_token_refresh_failed",
        ) from err

    websession = async_get_clientsession(hass)
    auth = AbetterrouteplannerAuth(session)
    client = AbrpClient(websession, ABRP_APP_KEY, auth)

    vehicles = await async_fetch_garage(client)

    device_registry = dr.async_get(hass)
    for raw, display in vehicles:
        scope = f"{entry.unique_id}_{raw.vehicle_id}"
        if display is None:
            _LOGGER.info(
                "No display metadata for vehicle %d (typecode %s); the device "
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

    # Deduplicated: the stream sends one comma-joined id list, which the v2
    # endpoint rejects as a whole if it is malformed.
    vehicle_ids = list(dict.fromkeys(raw.vehicle_id for raw, _ in vehicles))

    stream: TelemetryStream | None = None
    if vehicle_ids:
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
        entry.async_on_unload(stream.stop)

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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
