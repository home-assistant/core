"""The A Better Routeplanner integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus

from aioabrp import AbrpClient, TelemetryStream
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .auth import AbetterrouteplannerAuth
from .const import (
    ABRP_APP_KEY,
    CONF_KNOWN_VEHICLE_IDS,
    CONF_VEHICLE_IDS,
    DOMAIN,
    PREWARM_WINDOW_SECONDS,
)
from .coordinator import AbrpTelemetryCoordinator, AbrpVehiclesCoordinator
from .oauth import AbetterrouteplannerOAuth2Implementation

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Device-card manufacturer fallback when the catalog can't resolve a make.
# Used by BOTH the setup-time anchor and the on-refresh metadata propagation;
# they must agree or the propagation would rewrite the field on every poll.
_DEFAULT_MANUFACTURER = "A Better Routeplanner"

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

    ``stream`` is the push-telemetry SSE consumer owned by the entry. It is
    only created when the entry has live vehicle ids to stream; an entry with
    no streamable vehicles leaves it ``None``.
    """

    session: config_entry_oauth2_flow.OAuth2Session
    garage_coordinator: AbrpVehiclesCoordinator
    telemetry_coordinator: AbrpTelemetryCoordinator
    stream: TelemetryStream | None


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
    # SSE — and downstream listeners (``_propagate_device_metadata``,
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
            manufacturer=vehicle.device_manufacturer or _DEFAULT_MANUFACTURER,
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

        * ``name`` — an ABRP vehicle rename. ``name_by_user`` wins: once the
          user has overridden the device name in HA, ABRP renames are skipped.
        * ``model`` / ``manufacturer`` — these only resolve once the garage
          coordinator's self-healing catalog fetch finally succeeds (a delayed
          catalog or a newly-added model). They are integration-owned (no
          user-override concept), so they always track the anchor formula;
          before the catalog loads they read the raw typecode / the default
          manufacturer, and flip to the catalog values on the poll after the
          fetch succeeds.

        Each field is compared before writing so an unchanged poll is a no-op.
        """
        device_registry = dr.async_get(hass)
        for vehicle in garage_coordinator.data:
            scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
            device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
            if device is None:
                continue
            # ``UNDEFINED`` per field = "leave unchanged"; only the fields that
            # actually differ are passed, so an unchanged poll is a no-op.
            name: str | UndefinedType = UNDEFINED
            if device.name_by_user is None:
                candidate = vehicle.name or vehicle.vehicle_model
                if device.name != candidate:
                    name = candidate
            model: str | UndefinedType = UNDEFINED
            candidate_model = vehicle.device_model or vehicle.vehicle_model
            if device.model != candidate_model:
                model = candidate_model
            manufacturer: str | UndefinedType = UNDEFINED
            candidate_manufacturer = (
                vehicle.device_manufacturer or _DEFAULT_MANUFACTURER
            )
            if device.manufacturer != candidate_manufacturer:
                manufacturer = candidate_manufacturer
            if (
                name is not UNDEFINED
                or model is not UNDEFINED
                or manufacturer is not UNDEFINED
            ):
                device_registry.async_update_device(
                    device.id, name=name, model=model, manufacturer=manufacturer
                )

    entry.async_on_unload(
        garage_coordinator.async_add_listener(_propagate_device_metadata)
    )

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
        are removed immediately — user intent is unambiguous, and it is config-
        not poll-driven, so a failed garage fetch never defers it. Vehicles
        absent from the garage poll but still selected are removed only after
        ``_ABSENCE_THRESHOLD`` consecutive *successful* polls omit them.

        Only a successful poll carries trustworthy presence: a non-200 fetch
        leaves ``garage_coordinator.data`` at its last-good value, so when
        ``last_update_success`` is false the presence read is skipped entirely —
        it neither advances nor resets the ``misses`` counter. This means a lone
        upstream blip cannot orphan a device, and a blip mid-streak cannot
        fabricate the final miss. The counter resets whenever a successful poll
        shows the vehicle present again.
        """
        device_registry = dr.async_get(hass)
        expected = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
        poll_trusted = garage_coordinator.last_update_success
        present = {vehicle.vehicle_id for vehicle in garage_coordinator.data}
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            vehicle_id = _vehicle_id_from_device(entry, device)
            if vehicle_id is None:
                continue
            if vehicle_id not in expected:
                device_registry.async_remove_device(device.id)
                misses.pop(vehicle_id, None)
                telemetry_coordinator.forget_vehicle(vehicle_id)
                continue
            if not poll_trusted:
                continue
            if vehicle_id in present:
                misses.pop(vehicle_id, None)
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
        # Prefer restored sensor state (warms the gate without a network call);
        # poll one-shot only for vehicles with no restored snapshot (first init
        # or state pruned past the restore-state expiry). Imported locally:
        # ``sensor`` imports ``AbetterrouteplannerConfigEntry`` from this module,
        # so a top-level import here would form a circular import at load time.
        from .sensor import build_seed_from_restored_state  # noqa: PLC0415

        # The restored seed warms ONLY the stream's monotonicity gate — it is
        # deliberately NOT pushed into ``coordinator.data`` (no ``_apply_metrics``
        # / ``on_update`` call). Routing it through the coordinator would stamp a
        # fresh receipt-time ``last_reported_at`` onto values that may be hours
        # old, corrupting the freshness the attribute reports. Restored sensor
        # *display* is owned separately by the sensor platform's
        # eager-from-registry probe + ``RestoreSensor``. Do not "just seed the
        # coordinator too" — that reintroduces the freshness bug.
        seed = build_seed_from_restored_state(hass, entry, vehicle_ids)
        # ``unseeded`` is the complement of the seed: vehicles with no restored
        # wire_time to rebuild from — a brand-new vehicle on this install, a
        # fresh install (seed is ``{}`` so every vehicle is unseeded), or a
        # vehicle parked past the restore-state expiry. It does NOT alter the
        # seed; it only decides who still needs a one-shot poll. ``async_seed``
        # fills ``coordinator.data`` for those vehicles (initial display +
        # lazy entity creation), NOT the gate — their gate starts cold and
        # warms from their first live frames, which is correct since there is
        # no persisted history to protect.
        unseeded = [vid for vid in vehicle_ids if vid not in seed]
        if unseeded:
            await telemetry_coordinator.async_seed(client, unseeded)
        stream = TelemetryStream(
            websession,
            ABRP_APP_KEY,
            auth,
            vehicle_ids,
            on_update=telemetry_coordinator.on_update,
            on_connection_change=telemetry_coordinator.on_connection_change,
            name=entry.title,
            seed=seed,
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
