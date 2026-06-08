"""The A Better Routeplanner integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_KNOWN_VEHICLE_IDS,
    CONF_VEHICLE_IDS,
    DOMAIN,
    PREWARM_WINDOW_SECONDS,
)
from .coordinator import (
    AbrpTelemetryCoordinator,
    AbrpVehiclesCoordinator,
    _run_sse_loop,
)
from .oauth import AbetterrouteplannerOAuth2Implementation

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]

# Consecutive missing-from-garage polls before treating a vehicle as deleted
# upstream. Threshold 2 ≈ 20 minutes of patience — covers transient ABRP-side
# blips while keeping the ghost-device window short. User-deselection bypasses
# this entirely and removes the device on the next setup pass.
_ABSENCE_THRESHOLD = 2


def _vehicle_id_from_device(
    entry: ConfigEntry[AbrpData], device: dr.DeviceEntry
) -> int | None:
    """Return the vehicle_id encoded in a device's scoped identifier, or None.

    Devices are registered with ``(DOMAIN, f"{entry.unique_id}_{vehicle_id}")``.
    Returns ``None`` for any identifier that doesn't match that shape so
    foreign / migration-leftover rows are left untouched by the reconciliation
    listener.
    """
    prefix = f"{entry.unique_id}_"
    for domain, scope in device.identifiers:
        if domain != DOMAIN or not scope.startswith(prefix):
            continue
        try:
            return int(scope[len(prefix) :])
        except ValueError:
            return None
    return None


def _make_auto_add_listener(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    garage_coordinator: AbrpVehiclesCoordinator,
) -> Callable[[], None]:
    """Build the dynamic-devices auto-add listener for the given entry.

    ``reload_pending`` tracks vehicle ids whose reload has been scheduled but
    the actual unload + re-setup teardown hasn't run yet. Two production
    hazards motivate it:

    1. ``async_schedule_reload`` is non-blocking — it enqueues the unload for
       the next event loop tick. A second coordinator refresh racing in before
       that tick would naively re-evaluate the same ``new_vehicles`` /
       ``missing_devices`` set and schedule a *second* reload, doubling the
       entity-unavailability blip and wasting the SSE-restart cost.
    2. Rapid back-to-back polls with *different* new vehicles should coalesce
       into a single reload — the in-flight reload's first_refresh picks up
       whatever ``entry.data`` looks like at that point, including any
       additions written between the schedule and the teardown.

    Bounded by listener lifetime: the actual reload tears down this closure
    (``entry.async_on_unload`` runs the deregistration), so a successful
    reload always clears the state. Known limitation: a teardown that
    *fails* mid-unload would leave the set populated and silence further
    auto-add attempts on the still-loaded entry; HA's framework moves the
    entry to SETUP_ERROR / SETUP_RETRY in that path, which GCs the closure
    on the next re-setup attempt.
    """
    reload_pending: set[int] = set()

    @callback
    def _auto_add_new_vehicles() -> None:
        """Auto-onboard new ABRP vehicles and recover re-appeared devices.

        Two paths terminate in a single ``async_schedule_reload``:

        1. **Genuinely new** — vehicles present in the live garage but not yet
           in ``CONF_KNOWN_VEHICLE_IDS`` are added atomically to both
           ``CONF_VEHICLE_IDS`` (selection) and ``CONF_KNOWN_VEHICLE_IDS`` (decision
           history), then the entry is reloaded so the sensor platform
           re-runs against the expanded ID list and the SSE consumer restarts
           with the new stream URL.
        2. **Re-appearance recovery** — a selected vehicle whose device row
           is missing from the registry (the stale-devices threshold-miss
           cleanup removed it while ABRP was flaky, then it reappeared)
           triggers a reload without touching ``CONF_VEHICLE_IDS``; setup
           re-registers the device.

        Users who don't want a particular garage member deselect it via
        reconfigure; the vehicle then stays in ``CONF_KNOWN_VEHICLE_IDS`` but
        NOT in ``CONF_VEHICLE_IDS`` and this listener leaves it alone forever
        — preserving the spouse-vehicle / rental-vehicle escape hatch.

        NOT called eagerly at setup time. The first fire is on the next
        coordinator refresh, which avoids a setup-time reload loop and lets
        the config-flow / migration paths own the "known" set at startup.

        Performs the deferred-migration seed when setup observed an empty
        first refresh: on the first non-empty poll, populate
        ``CONF_KNOWN_VEHICLE_IDS`` from the live garage and return. Seeding
        immediately on empty would have written ``KNOWN=[]`` and re-onboarded
        every pre-upgrade-deselected vehicle once the garage repopulated.
        """
        if CONF_KNOWN_VEHICLE_IDS not in entry.data:
            if not garage_coordinator.data:
                return
            # Freeze-at-first-observation: a vehicle added to ABRP between
            # pre-upgrade and this first non-empty poll is baked into KNOWN
            # as "declined", and onboarding it requires the user to
            # reconfigure. Accepted trade-off — the alternative (treat the
            # gap as still-empty) would mass-onboard every pre-upgrade-
            # deselected vehicle if the outage spans multiple cycles.
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_KNOWN_VEHICLE_IDS: sorted(
                        str(vehicle.vehicle_id) for vehicle in garage_coordinator.data
                    ),
                },
            )
            return

        known = {int(v) for v in entry.data[CONF_KNOWN_VEHICLE_IDS]}
        selected = {int(v) for v in entry.data[CONF_VEHICLE_IDS]}
        present = {vehicle.vehicle_id for vehicle in garage_coordinator.data}

        new_vehicles = present - known

        device_registry = dr.async_get(hass)
        existing_devices: set[int] = set()
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            vehicle_id = _vehicle_id_from_device(entry, device)
            if vehicle_id is not None:
                existing_devices.add(vehicle_id)
        expected_devices = (selected | new_vehicles) & present
        missing_devices = expected_devices - existing_devices

        # Vehicles that haven't already been covered by a still-pending reload
        # — either a brand-new addition or a missing device we haven't yet
        # asked HA to recover. An empty result means nothing actionable.
        triggering = (new_vehicles | missing_devices) - reload_pending
        if not triggering:
            return

        if new_vehicles:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_VEHICLE_IDS: sorted(str(v) for v in selected | new_vehicles),
                    CONF_KNOWN_VEHICLE_IDS: sorted(
                        str(v) for v in known | new_vehicles
                    ),
                },
            )

        # Schedule the reload only when no reload is already in flight; an
        # already-scheduled teardown will pick up the updated ``entry.data``
        # via its post-unload setup pass. ``reload_pending`` is updated
        # regardless so a successful reload's listener teardown clears the
        # accumulated state in one shot.
        already_pending = bool(reload_pending)
        reload_pending.update(new_vehicles | missing_devices)
        if not already_pending:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    return _auto_add_new_vehicles


@dataclass(frozen=True, slots=True)
class AbrpData:
    """Runtime data stored on the config entry.

    Two coordinators live side by side: the garage coordinator polls
    ``/1/session/get_tlm`` every 10 minutes for vehicle identity (stable,
    drives device-registry entries), while the telemetry coordinator
    receives push updates from the ``/2/tlm`` SSE stream. Separating them
    isolates failure modes — SSE flakes never threaten device identity.
    """

    session: config_entry_oauth2_flow.OAuth2Session
    garage_coordinator: AbrpVehiclesCoordinator
    telemetry_coordinator: AbrpTelemetryCoordinator


type AbetterrouteplannerConfigEntry = ConfigEntry[AbrpData]


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

    if CONF_KNOWN_VEHICLE_IDS not in entry.data and garage_coordinator.data:
        # Additive field with a live-seeded default — deliberately no VERSION
        # bump and no ``async_migrate_entry``. Seed from the garage AFTER the
        # first refresh so pre-existing entries treat every currently-visible
        # vehicle as "known"; pre-upgrade-deselected vehicles therefore remain
        # known-but-not-selected (i.e. declined) and the auto-add listener
        # below will leave them alone.
        #
        # Skip the seed when ``garage_coordinator.data`` is empty: a transient
        # ABRP outage / rate-limit at first refresh would otherwise write
        # ``KNOWN=[]``, and the next non-empty poll would treat every
        # pre-upgrade-deselected vehicle as "new" and auto-onboard it. The
        # listener below performs the deferred seed on the first non-empty
        # poll instead.
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_KNOWN_VEHICLE_IDS: sorted(
                    str(vehicle.vehicle_id) for vehicle in garage_coordinator.data
                ),
            },
        )

    # Anchor a device per selected vehicle BEFORE forwarding the platforms and
    # registering the garage-listener callbacks. The device card is then
    # present immediately after setup — even for a vehicle that's silent on
    # SSE — and downstream listeners (``_propagate_renames``,
    # ``_remove_stale_devices``) operate against a populated device registry
    # on their first fire. Formulas mirror those used by the telemetry
    # entities so the device fields match what an entity-driven registration
    # would have produced.
    device_registry = dr.async_get(hass)
    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
    for vehicle in garage_coordinator.data:
        if vehicle.vehicle_id not in selected_ids:
            continue
        scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, scope)},
            manufacturer=vehicle.device_manufacturer or "A Better Routeplanner",
            model=vehicle.device_model or vehicle.vehicle_model,
            name=vehicle.name or vehicle.vehicle_model,
            configuration_url=(
                f"https://abetterrouteplanner.com/?vehicle_id={vehicle.vehicle_id}"
            ),
        )

    @callback
    def _propagate_renames() -> None:
        """Push ABRP vehicle-name changes into the HA device registry.

        Fires on every successful garage refresh. The same expression as
        ``DeviceInfo.name`` in :mod:`.sensor` (``vehicle.name`` with a
        ``vehicle_model`` fallback) is recomputed each call so the registry
        entry stays in lockstep with what the initial registration would
        have produced. ``name_by_user`` wins — once the user has overridden
        the device name in HA, ABRP renames are silently skipped.
        """
        device_registry = dr.async_get(hass)
        for vehicle in garage_coordinator.data:
            scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
            device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
            if device is None:
                continue
            if device.name_by_user is not None:
                continue
            new_name = vehicle.name or vehicle.vehicle_model
            if device.name == new_name:
                continue
            device_registry.async_update_device(device.id, name=new_name)

    entry.async_on_unload(garage_coordinator.async_add_listener(_propagate_renames))

    # Construct the telemetry coordinator BEFORE the stale-devices listener
    # closure captures it — the listener fires both eagerly at setup time
    # (line below) and on every garage refresh, and invokes
    # ``forget_vehicle`` to keep the per-vehicle telemetry maps honest
    # with the device registry.
    telemetry_coordinator = AbrpTelemetryCoordinator(hass, entry)

    misses: dict[int, int] = {}

    @callback
    def _remove_stale_devices() -> None:
        """Reconcile the device registry against ``selected ∩ present``.

        User-deselected vehicles (no longer in ``entry.data[CONF_VEHICLE_IDS]``)
        are removed immediately — user intent is unambiguous. Vehicles
        absent from the garage poll but still selected are removed only
        after ``_ABSENCE_THRESHOLD`` consecutive misses, so a single
        transient upstream blip cannot orphan a device. The ``misses``
        counter resets whenever the vehicle reappears.
        """
        device_registry = dr.async_get(hass)
        expected = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
        present = {vehicle.vehicle_id for vehicle in garage_coordinator.data}
        authoritative = expected & present
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            vehicle_id = _vehicle_id_from_device(entry, device)
            if vehicle_id is None:
                continue
            if vehicle_id in authoritative:
                misses.pop(vehicle_id, None)
                continue
            if vehicle_id not in expected:
                device_registry.async_remove_device(device.id)
                misses.pop(vehicle_id, None)
                telemetry_coordinator.forget_vehicle(vehicle_id)
                continue
            misses[vehicle_id] = misses.get(vehicle_id, 0) + 1
            if misses[vehicle_id] >= _ABSENCE_THRESHOLD:
                device_registry.async_remove_device(device.id)
                misses.pop(vehicle_id, None)
                telemetry_coordinator.forget_vehicle(vehicle_id)

    # Eager setup-time pass clears user-deselected devices before the sensor
    # platform forwards entities, so a reload after reconfigure never leaves
    # ghost devices visible for the 10-min poll interval.
    _remove_stale_devices()
    entry.async_on_unload(garage_coordinator.async_add_listener(_remove_stale_devices))

    entry.async_on_unload(
        garage_coordinator.async_add_listener(
            _make_auto_add_listener(hass, entry, garage_coordinator)
        )
    )

    entry.runtime_data = AbrpData(
        session=session,
        garage_coordinator=garage_coordinator,
        telemetry_coordinator=telemetry_coordinator,
    )

    # Spawn the SSE consumer scoped to the entry's selected vehicles. The
    # task is owned by the config entry — HA cancels it on unload. Filter
    # the selection against the live garage so we only stream for vehicles
    # the API actually knows about; the v2 endpoint rejects unknown IDs,
    # and an entry with no live selections (e.g. user removed every vehicle
    # in ABRP) should idle until the next garage refresh re-discovers them.
    present_ids = {vehicle.vehicle_id for vehicle in garage_coordinator.data}
    vehicle_ids = [
        int(vehicle_id)
        for vehicle_id in entry.data[CONF_VEHICLE_IDS]
        if int(vehicle_id) in present_ids
    ]
    # Seed the telemetry coordinator BEFORE spawning the SSE consumer so the
    # cached JSON snapshot is the baseline the stream merges into; then give
    # the consumer a brief pre-warm window before forwarding to the sensor
    # platform. The JSON snapshot can lag the live stream (e.g. a vehicle is
    # charging right now → ``power`` is non-null on SSE but null in the
    # cached JSON), so the window lets in-flight frames merge into
    # ``coordinator.data`` before the platform inspects it to decide which
    # metric entities to create. The wait is capped: a slow / empty stream
    # falls through to the dispatcher path, which covers any post-setup
    # first-arrival.
    if vehicle_ids:
        await telemetry_coordinator.async_seed_from_json_poll(
            vehicle_ids, session.token["access_token"]
        )
        entry.async_create_background_task(
            hass,
            _run_sse_loop(hass, entry, telemetry_coordinator, session, vehicle_ids),
            name="abrp-sse",
        )
        await asyncio.sleep(PREWARM_WINDOW_SECONDS)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AbetterrouteplannerConfigEntry
) -> bool:
    """Unload a config entry."""
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
