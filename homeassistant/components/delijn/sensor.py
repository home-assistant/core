"""Sensor for De Lijn (Flemish public transport) departure information."""

import asyncio
from datetime import datetime
from types import MappingProxyType
from typing import Any, override

from pydelijn import (
    DeLijnAuthError,
    DeLijnClient,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    Passage,
    Stop,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    CONF_SUBENTRIES,
    DATA_FAILED_IMPORT_STOPS,
    DATA_IMPORT_LOCK,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    SUBENTRY_TYPE_STOP,
)
from .coordinator import DeLijnConfigEntry, DeLijnCoordinator
from .util import stop_delijn_url, stop_title

PARALLEL_UPDATES = 0

CONF_NEXT_DEPARTURE = "next_departure"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)


def _find_entry_by_api_key(
    hass: HomeAssistant, api_key: str
) -> DeLijnConfigEntry | None:
    """Return the existing De Lijn entry using this API key, if any."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_API_KEY] == api_key:
            return entry
    return None


def _is_stop_on_entry(entry: DeLijnConfigEntry, stop_number: str) -> bool:
    """Return whether a stop is already configured as a subentry of entry."""
    return any(
        subentry.unique_id == stop_number for subentry in entry.subentries.values()
    )


def _is_stop_on_any_entry(hass: HomeAssistant, stop_number: str) -> bool:
    """Return whether a stop is already configured on any De Lijn entry.

    Sensor unique ids are scoped to the stop number only, so the same stop
    configured on two entries would collide; it must be treated as a single
    global account-independent resource.
    """
    return any(
        _is_stop_on_entry(entry, stop_number)
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


def _get_failed_import_stops(hass: HomeAssistant) -> set[tuple[str, str]]:
    """Return the set of (api_key, stop_id) pairs that failed to import.

    Shared across YAML platform blocks and keyed by account so that one
    account's success can't hide another account's still-failing stop.
    This cannot live on a single config entry's runtime_data since it
    tracks failures across separate accounts (API keys) and even across a
    YAML block whose entry doesn't exist yet.
    """
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_FAILED_IMPORT_STOPS, set())


def _get_import_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the lock serializing YAML platform imports across all blocks.

    Concurrent import blocks that share an API key could otherwise both
    pass validation for the same stop and race to add it as a subentry;
    the loser's ``async_add_subentry`` call raises ``AbortFlow``, aborting
    that block's import before its repair-issue bookkeeping runs.
    """
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_IMPORT_LOCK, asyncio.Lock())


def _build_subentry_data(stop: Stop, number_of_departures: int) -> ConfigSubentryData:
    """Return the ConfigSubentryData for a validated stop."""
    return ConfigSubentryData(
        data={
            CONF_STOP_NUMBER: stop.number,
            CONF_NUMBER_OF_DEPARTURES: number_of_departures,
        },
        subentry_type=SUBENTRY_TYPE_STOP,
        title=stop_title(stop),
        unique_id=stop.number,
    )


async def _async_add_subentries_to_entry(
    hass: HomeAssistant,
    entry: DeLijnConfigEntry,
    to_add: list[tuple[Stop, int]],
) -> None:
    """Add subentries to an existing entry with exactly one reload.

    Unloading first (when currently loaded) removes the update listener
    registered via ``entry.async_on_unload``, so the additions below don't
    each queue their own reload; a single explicit reload applies them all.

    Unloading awaits, so a concurrent subentry flow (e.g. from the UI)
    could add one of these stops in the meantime, on this entry or on a
    different one (sensor unique ids are global); ``async_add_subentry``
    raises ``AbortFlow`` on a duplicate unique_id, so every stop is
    re-checked against all entries' subentries immediately before it is
    added, and skipped if it's already configured anywhere.
    """
    if entry.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(entry.entry_id)
    for stop, number_of_departures in to_add:
        if _is_stop_on_any_entry(hass, stop.number):
            continue
        subentry_data = _build_subentry_data(stop, number_of_departures)
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(subentry_data["data"]),
                subentry_type=subentry_data["subentry_type"],
                title=subentry_data["title"],
                unique_id=subentry_data["unique_id"],
            ),
        )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration into config entries.

    One main entry is used per API key; each configured stop becomes a
    subentry of it. Subentries can only be created from a user-initiated
    flow, so each stop is validated here and added directly.

    Adding a subentry to an already-loaded entry queues a reload via the
    entry's update listener; importing several stops one at a time would
    then queue one reload per stop, each re-fetching every stop from the
    API. Every stop is therefore validated first (the only part that
    awaits), and the resulting subentries are only ever added by
    ``_async_add_subentries_to_entry``, which guarantees exactly one setup
    of the complete final state: a brand new entry is created with all of
    its subentries atomically via ``async_create_entry(subentries=...)``, so
    the entry is set up once with everything already present; adding stops
    to an entry that already exists removes its update listener by
    unloading first, so nothing reloads until the explicit reload at the end.

    Multiple YAML platform blocks run as separate, concurrently scheduled
    setup tasks. With the same API key and an overlapping stop, both could
    otherwise pass validation before either commits it, and the loser of
    the resulting ``async_add_subentry`` race would raise ``AbortFlow``,
    aborting that whole block's import before its repair-issue bookkeeping
    ran. The entire import body therefore runs under a single lock shared
    by all blocks.
    """
    async with _get_import_lock(hass):
        await _async_import_platform(hass, config)


async def _async_import_platform(hass: HomeAssistant, config: ConfigType) -> None:
    """Run one YAML platform block's import, serialized by the caller."""
    api_key = config[CONF_API_KEY]
    entry = _find_entry_by_api_key(hass, api_key)

    client = DeLijnClient(api_key, async_get_clientsession(hass))
    failed_stops = _get_failed_import_stops(hass)
    to_add: list[tuple[Stop, int]] = []
    pending_numbers: set[str] = set()
    stop_ids_by_number: dict[str, str] = {}

    for departure in config[CONF_NEXT_DEPARTURE]:
        stop_id = departure[CONF_STOP_ID]
        issue_id = f"deprecated_yaml_import_issue_{stop_id}"

        if _is_stop_on_any_entry(hass, stop_id) or stop_id in pending_numbers:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            failed_stops.discard((api_key, stop_id))
            continue

        try:
            stop = await client.get_stop(stop_id)
        except DeLijnNotFoundError:
            reason: str | None = "invalid_stop"
        except DeLijnAuthError as err:
            LOGGER.error(
                "De Lijn rejected the API key while importing stop %s: %s",
                stop_id,
                err,
            )
            reason = "invalid_auth"
        except DeLijnConnectionError as err:
            LOGGER.error(
                "Error connecting to the De Lijn API while importing stop %s: %s",
                stop_id,
                err,
            )
            reason = "cannot_connect"
        except DeLijnError:
            LOGGER.exception("Unexpected error importing De Lijn stop %s", stop_id)
            reason = "unknown"
        else:
            reason = None

        if reason is not None:
            failed_stops.add((api_key, stop_id))
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "De Lijn",
                    "stop_id": stop_id,
                },
            )
            continue

        # A successful import, or one already configured in a prior
        # restart, resolves any previously reported import failure.
        failed_stops.discard((api_key, stop_id))
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        if _is_stop_on_any_entry(hass, stop.number) or stop.number in pending_numbers:
            continue

        pending_numbers.add(stop.number)
        stop_ids_by_number[stop.number] = stop_id
        to_add.append((stop, departure[CONF_NUMBER_OF_DEPARTURES]))

    if entry is None and to_add:
        # Validating every stop above is the only part that awaits; a UI
        # subentry flow could have added one of them to a different entry
        # in that window (sensor unique ids are global), before this brand
        # new entry is created with them as subentries.
        still_pending: list[tuple[Stop, int]] = []
        for stop, number_of_departures in to_add:
            if _is_stop_on_any_entry(hass, stop.number):
                dup_stop_id = stop_ids_by_number[stop.number]
                ir.async_delete_issue(
                    hass, DOMAIN, f"deprecated_yaml_import_issue_{dup_stop_id}"
                )
                failed_stops.discard((api_key, dup_stop_id))
                continue
            still_pending.append((stop, number_of_departures))
        to_add = still_pending

    if to_add:
        if entry is None:
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_API_KEY: api_key,
                    CONF_SUBENTRIES: [
                        _build_subentry_data(stop, number_of_departures)
                        for stop, number_of_departures in to_add
                    ],
                },
            )
            if result.get("type") is not FlowResultType.CREATE_ENTRY:
                # A race created the entry between our lookup and this call.
                entry = _find_entry_by_api_key(hass, api_key)
                assert entry is not None
                await _async_add_subentries_to_entry(hass, entry, to_add)
        else:
            await _async_add_subentries_to_entry(hass, entry, to_add)

    generic_issue_id = f"deprecated_yaml_{DOMAIN}"
    if failed_stops:
        # Don't tell the user to remove the YAML config while a stop still
        # needs it to retry; drop any stale notice from an earlier restart.
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, generic_issue_id)
    else:
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            generic_issue_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "De Lijn",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeLijnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the De Lijn sensors from a config entry, one per stop subentry."""
    for subentry_id, coordinator in entry.runtime_data.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [DeLijnSensor(coordinator, subentry)], config_subentry_id=subentry_id
        )


def _due_in_minutes(due_at: datetime | None) -> int | None:
    """Return the number of whole minutes from now until due_at."""
    if due_at is None:
        return None
    return int((due_at - dt_util.utcnow()).total_seconds() / 60)


def _legacy_transport_type(transport_type: str | None) -> str | None:
    """Return a line's transport type in the uppercase form pydelijn 1.x used."""
    if transport_type is None:
        return None
    return transport_type.upper()


def _bare_hex(colour: str | None) -> str | None:
    """Return a colour hex value without the leading #.

    The pre-config-flow integration exposed colours this way, and community
    dashboard cards prepend the # themselves.
    """
    if colour is None:
        return None
    return colour.removeprefix("#")


def _passage_attributes(index: int, passage: Passage) -> dict[str, Any]:
    """Return the legacy attribute mapping for a single passage."""
    line = passage.line
    return {
        "passage": index,
        "line_number": line.number,
        "direction": passage.direction,
        "final_destination": passage.destination,
        "due_at_schedule": (
            passage.due_at_schedule.isoformat() if passage.due_at_schedule else None
        ),
        "due_at_realtime": (
            passage.due_at_realtime.isoformat() if passage.due_at_realtime else None
        ),
        "due_in_min": _due_in_minutes(passage.due_at),
        "is_realtime": passage.is_realtime,
        "cancelled": passage.cancelled,
        "line_number_public": line.public_number,
        "line_desc": line.description,
        "line_transport_type": _legacy_transport_type(line.transport_type),
        "line_number_colourFront": _bare_hex(line.colour_front_hex),
        "line_number_colourFrontHex": _bare_hex(line.colour_front_hex),
        "line_number_colourBack": _bare_hex(line.colour_back_hex),
        "line_number_colourBackHex": _bare_hex(line.colour_back_hex),
        "line_number_colourFrontBorder": _bare_hex(line.colour_front_border_hex),
        "line_number_colourFrontBorderHex": _bare_hex(line.colour_front_border_hex),
        "line_number_colourBackBorder": _bare_hex(line.colour_back_border_hex),
        "line_number_colourBackBorderHex": _bare_hex(line.colour_back_border_hex),
    }


class DeLijnSensor(CoordinatorEntity[DeLijnCoordinator], SensorEntity):
    """Representation of the next De Lijn departure at a stop."""

    _attr_attribution = "Data provided by data.delijn.be"
    _attr_has_entity_name = True
    _attr_translation_key = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: DeLijnCoordinator, subentry: ConfigSubentry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        stop_number = subentry.data[CONF_STOP_NUMBER]
        self._stopname = subentry.title
        self._attr_unique_id = f"{stop_number}_next_departure"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_number)},
            name=subentry.title,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=stop_delijn_url(stop_number),
            model="Stop",
            model_id=stop_number,
        )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the due time of the next passage."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data[0].due_at

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return backward-compatible attributes for the community Lovelace card."""
        passages = self.coordinator.data
        if not passages:
            return {
                "stopname": self._stopname,
                "line_number_public": None,
                "line_transport_type": None,
                "final_destination": None,
                "due_at_schedule": None,
                "due_at_realtime": None,
                "is_realtime": None,
                "cancelled": None,
                "next_passages": [],
            }

        first = passages[0]
        return {
            "stopname": self._stopname,
            "line_number_public": first.line.public_number,
            "line_transport_type": _legacy_transport_type(first.line.transport_type),
            "final_destination": first.destination,
            "due_at_schedule": (
                first.due_at_schedule.isoformat() if first.due_at_schedule else None
            ),
            "due_at_realtime": (
                first.due_at_realtime.isoformat() if first.due_at_realtime else None
            ),
            "is_realtime": first.is_realtime,
            "cancelled": first.cancelled,
            "next_passages": [
                _passage_attributes(index, passage)
                for index, passage in enumerate(passages)
            ],
        }
