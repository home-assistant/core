"""The A Better Routeplanner integration."""

import logging

from aioabrp import AbrpClient, TelemetryStream

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import AbrpAuth
from .const import ABRP_APP_KEY, DOMAIN
from .coordinator import (
    AbrpConfigEntry,
    AbrpData,
    AbrpTelemetryCoordinator,
    async_fetch_garage,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AbrpConfigEntry) -> None:
    """Set up A Better Routeplanner from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # The helper maps token errors to setup errors, but not a bare timeout.
    try:
        await session.async_ensure_token_valid()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_token_refresh_failed",
        ) from err

    websession = async_get_clientsession(hass)
    auth = AbrpAuth(session)
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

        # Entries are not unloaded on shutdown, so stop the stream there too.
        async def _async_stop_stream(_: Event) -> None:
            await stream.stop()

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_stream)
        )

    entry.runtime_data = AbrpData(
        vehicles=vehicles, telemetry_coordinator=telemetry_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AbrpConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
