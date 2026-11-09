"""The A Better Routeplanner integration."""

import logging

from aioabrp import AbrpClient, TelemetryStream

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import Undefined

from .auth import AbrpAuth
from .const import ABRP_APP_KEY, DOMAIN
from .coordinator import (
    AbrpConfigEntry,
    AbrpData,
    AbrpGarageCoordinator,
    AbrpTelemetryCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]


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

    garage_coordinator = AbrpGarageCoordinator(hass, entry, client)
    await garage_coordinator.async_config_entry_first_refresh()

    telemetry_coordinator = AbrpTelemetryCoordinator(hass, entry)
    stream = TelemetryStream(
        websession,
        ABRP_APP_KEY,
        auth,
        [],
        on_update=telemetry_coordinator.on_update,
        on_connection_change=telemetry_coordinator.on_connection_change,
        name=entry.title,
    )

    device_registry = dr.async_get(hass)
    known: set[int] = set()

    @callback
    def _async_add_new_vehicles() -> None:
        """Create a device per garage vehicle, then subscribe the stream to new ones."""
        for raw, display in garage_coordinator.data:
            scope = f"{entry.unique_id}_{raw.vehicle_id}"
            manufacturer: str | Undefined | None = Undefined
            model: str | Undefined | None = Undefined
            if display is not None:
                manufacturer, model = display.manufacturer, display.model_name
            elif raw.vehicle_id not in known:
                # A known vehicle keeps what an earlier poll resolved.
                model = raw.vehicle_model
                _LOGGER.info(
                    "No display metadata for vehicle %d (typecode %s); the device "
                    "shows the raw typecode until a later garage check resolves it",
                    raw.vehicle_id,
                    raw.vehicle_model,
                )
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, scope)},
                manufacturer=manufacturer,
                model=model,
                name=raw.name or raw.vehicle_model,
                configuration_url=(
                    f"https://abetterrouteplanner.com/?vehicle_id={raw.vehicle_id}"
                ),
            )
        # Add-only: vehicles that leave the garage stay until the entry reloads.
        known.update(raw.vehicle_id for raw, _ in garage_coordinator.data)
        stream.set_vehicle_ids(known)

    _async_add_new_vehicles()
    await stream.start()
    entry.async_on_unload(stream.stop)

    # Entries are not unloaded on shutdown, so stop the stream there too.
    async def _async_stop_stream(_: Event) -> None:
        await stream.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_stream)
    )

    entry.runtime_data = AbrpData(
        garage_coordinator=garage_coordinator,
        telemetry_coordinator=telemetry_coordinator,
    )
    entry.async_on_unload(
        garage_coordinator.async_add_listener(_async_add_new_vehicles)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AbrpConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
