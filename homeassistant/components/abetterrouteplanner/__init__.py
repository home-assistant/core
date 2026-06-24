"""The A Better Routeplanner integration."""

import asyncio
from http import HTTPStatus

from aioabrp import AbrpClient, TelemetryStream
from aiohttp import ClientError, ClientResponseError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .auth import AbetterrouteplannerAuth
from .const import ABRP_APP_KEY, CONF_VEHICLE_IDS, DOMAIN, PREWARM_WINDOW_SECONDS
from .coordinator import (
    AbetterrouteplannerConfigEntry,
    AbrpData,
    AbrpTelemetryCoordinator,
    AbrpVehiclesCoordinator,
)
from .oauth import AbetterrouteplannerOAuth2Implementation
from .sensor import vehicles_without_sensors

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

    garage_coordinator = AbrpVehiclesCoordinator(hass, entry, session)
    await garage_coordinator.async_config_entry_first_refresh()

    # Anchor a device per selected vehicle BEFORE forwarding the platforms and
    # registering the garage-listener callbacks. The device card is then
    # present immediately after setup — even for a vehicle that's silent on
    # SSE — and the ``_propagate_device_metadata`` listener operates against a
    # populated device registry on its first fire. Formulas mirror those used
    # by the telemetry entities so the device fields match what an
    # entity-driven registration would have produced.
    device_registry = dr.async_get(hass)
    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
    for vehicle in garage_coordinator.data:
        if vehicle.vehicle_id not in selected_ids:
            continue
        scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, scope)},
            manufacturer=vehicle.device_manufacturer,
            model=vehicle.device_model or vehicle.vehicle_model,
            name=vehicle.name or vehicle.vehicle_model,
            configuration_url=(
                f"https://abetterrouteplanner.com/?vehicle_id={vehicle.vehicle_id}"
            ),
        )

    @callback
    def _propagate_device_metadata() -> None:
        """Reconcile each device's name, model, and manufacturer on refresh.

        Fires on every successful garage refresh and recomputes the same
        expressions the setup-time anchor used, so any value that changes
        upstream is pushed into the registry WITHOUT a config-entry reload:

        * ``name`` — an ABRP vehicle rename.
        * ``model`` / ``manufacturer`` — recomposed from the per-vehicle
          display fetch each poll. They are integration-owned (no
          user-override concept), so they always track the anchor formula:
          on a display hit they carry the composed model + manufacturer, and
          on a display miss/failure ``model`` falls back to the raw typecode
          and ``manufacturer`` is left unset, recomposing when the fetch next
          succeeds.

        ``async_update_device`` diffs each field and no-ops (no event, no
        save) when nothing changed, so an unchanged poll is a no-op.
        """
        device_registry = dr.async_get(hass)
        for vehicle in garage_coordinator.data:
            scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
            device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
            if device is None:
                continue
            device_registry.async_update_device(
                device.id,
                name=vehicle.name or vehicle.vehicle_model,
                model=vehicle.device_model or vehicle.vehicle_model,
                manufacturer=vehicle.device_manufacturer,
            )

    entry.async_on_unload(
        garage_coordinator.async_add_listener(_propagate_device_metadata)
    )

    telemetry_coordinator = AbrpTelemetryCoordinator(hass, entry)

    # Build the auth wrapper + client + websession once; they back both the
    # seed poll and the SSE consumer below. The stream is owned by the config
    # entry and stopped on unload.
    websession = async_get_clientsession(hass)
    auth = AbetterrouteplannerAuth(session)
    client = AbrpClient(websession, ABRP_APP_KEY, auth)

    # Filter the selection against the live garage so we only stream for
    # vehicles the API actually knows about; the v2 endpoint rejects unknown
    # IDs, and an entry with no live selections (e.g. user removed every
    # vehicle in ABRP) should idle until the next garage refresh re-discovers
    # them.
    present_ids = {vehicle.vehicle_id for vehicle in garage_coordinator.data}
    vehicle_ids = [
        int(vehicle_id)
        for vehicle_id in entry.data[CONF_VEHICLE_IDS]
        if int(vehicle_id) in present_ids
    ]

    # Seed the telemetry coordinator BEFORE starting the stream so the cached
    # snapshot is the baseline the stream merges into; then give the consumer
    # a brief pre-warm window before forwarding to the sensor platform. The
    # seeded snapshot can lag the live stream (e.g. a vehicle is charging right
    # now → ``power`` is non-null on SSE but null in the seed), so the window
    # lets in-flight frames merge into ``coordinator.data`` before the platform
    # inspects it to decide which metric entities to create. The wait is
    # capped: a slow / empty stream falls through to the dispatcher path, which
    # covers any post-setup first-arrival.
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
        await asyncio.sleep(PREWARM_WINDOW_SECONDS)

    entry.runtime_data = AbrpData(
        session=session,
        garage_coordinator=garage_coordinator,
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
    """Allow the HA UI's "Delete from this integration" link for any device.

    Always returns ``True`` — even for a vehicle still in the
    ``selected ∩ present`` set. If the user removes an active device the row
    stays gone until the next entry reload (handled by the standard re-register
    path on setup), which is the expected escape hatch behaviour.
    """
    return True
