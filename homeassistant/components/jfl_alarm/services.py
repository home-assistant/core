"""The service layer — the things an automation needs that no entity models.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**Registered in `async_setup`, not `async_setup_entry`** — AGENTS.md §5. Services registered per
entry disappear when the entry is unloaded, and an automation that references one then fails
validation for a reason that has nothing to do with the automation.

Each service exists because it is genuinely not an entity:

* `sync_time` — an *action* on the panel's clock. A `datetime` entity would imply the clock is
  readable as state and settable at leisure; it is neither.
* `refresh_status` — the panel-wide version of the refresh button, callable per config entry.
* `set_bypass_mask` — replaces the whole bypass bitmap at once. The per-zone switches are the
  ordinary way in; this is for "clear every bypass", which fifteen switch calls express badly.

Every one of them goes through the coordinator's two gates, so `read_only` and the commands switch
mean what they say no matter how the panel is reached.
"""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from pyjfl import ContactIdCode, EventRecord, EventSubject, lookup
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DEFAULT_EVENT_LIMIT, DOMAIN, LOGGER, MAX_EVENT_LIMIT

if TYPE_CHECKING:
    from . import JflConfigEntry, JflRuntimeData
    from .coordinator import JflPanelCoordinator

SERVICE_SYNC_TIME = "sync_time"
SERVICE_REFRESH_STATUS = "refresh_status"
SERVICE_SET_BYPASS_MASK = "set_bypass_mask"
SERVICE_READ_PROGRAMMING = "read_programming"
SERVICE_READ_EVENT_BUFFER = "read_event_buffer"

ATTR_ZONES = "zones"
ATTR_SINCE_SERIAL = "since_serial"
ATTR_LIMIT = "limit"

type _Action = Callable[
    ["JflPanelCoordinator", ServiceCall], Coroutine[Any, Any, ServiceResponse]
]
"""What every service body looks like: given the target panel and the call, do the thing."""

type _Handler = Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]
"""What Home Assistant registers: the same thing with the panel already resolved."""

_TARGET_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

_SET_BYPASS_MASK_SCHEMA = _TARGET_SCHEMA.extend(
    {
        # An **empty list is the point**, not an accident: it is how every bypass is cleared, and
        # the captured frame for that is thirteen zero bytes. `vol.Length(min=1)` would forbid the
        # one call this service is most useful for.
        vol.Required(ATTR_ZONES): vol.All(
            cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=99))]
        )
    }
)

_READ_EVENT_BUFFER_SCHEMA = _TARGET_SCHEMA.extend(
    {
        # The buffer pages **forward from oldest**, so resuming is the only way to reach the newest
        # records without re-reading everything: keep the highest `serial` a call returned and pass
        # it back here next time.
        vol.Optional(ATTR_SINCE_SERIAL, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=0xFFFFFFFF)
        ),
        vol.Optional(ATTR_LIMIT, default=DEFAULT_EVENT_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_EVENT_LIMIT)
        ),
    }
)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register every service. Called once from `async_setup`, whatever entries exist."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_TIME,
        _make_handler(hass, _sync_time),
        schema=_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_STATUS,
        _make_handler(hass, _refresh_status),
        schema=_TARGET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BYPASS_MASK,
        _make_handler(hass, _set_bypass_mask),
        schema=_SET_BYPASS_MASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_PROGRAMMING,
        _make_handler(hass, _read_programming),
        schema=_TARGET_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_EVENT_BUFFER,
        _make_handler(hass, _read_event_buffer),
        schema=_READ_EVENT_BUFFER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def _make_handler(hass: HomeAssistant, action: _Action) -> _Handler:
    """Wrap *action* so it receives the coordinator the call's device belongs to."""

    async def _handle(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for(hass, call)
        return await action(coordinator, call)

    return _handle


async def _sync_time(
    coordinator: JflPanelCoordinator, call: ServiceCall
) -> ServiceResponse:
    """Set the panel's clock to Home Assistant's local time.

    Local, not UTC: the panel has no timezone and displays whatever it is given, so sending UTC
    would timestamp every event it reports from then on by however far the user is from Greenwich.
    """
    await coordinator.async_sync_time(dt_util.now())
    return None


async def _refresh_status(
    coordinator: JflPanelCoordinator, call: ServiceCall
) -> ServiceResponse:
    """Ask the panel for a status frame. A *read*, so it works in read-only mode."""
    await coordinator.async_refresh_status()
    return None


async def _set_bypass_mask(
    coordinator: JflPanelCoordinator, call: ServiceCall
) -> ServiceResponse:
    """Replace the whole manual-bypass bitmap with exactly the zones given."""
    zones = frozenset(call.data[ATTR_ZONES])
    await coordinator.async_set_bypass_mask(zones)
    return None


async def _read_event_buffer(
    coordinator: JflPanelCoordinator, call: ServiceCall
) -> ServiceResponse:
    """Return the panel's own event memory — the history no Home Assistant entity holds.

    **A read**, so it works in read-only mode, like the status poll and the programming read.

    ⚠️ **Nothing here is fired at the `event` entities, deliberately.** An `event` entity firing is
    a live occurrence: automations run and notifications go out, so replaying a stored `1120` is a
    panic button pressing itself. This returns *data* for the caller to look at, which is the only
    honest thing to do with a log of things that already happened. `coordinator.async_read_events`
    says the same at the layer below.

    Each record is returned with its Contact ID description and, where the panel's programming names
    the subject, the zone or user **name** — the same resolution the live events got in Sprint 8.5.
    """
    records = await coordinator.async_read_events(
        since=int(call.data[ATTR_SINCE_SERIAL]), limit=int(call.data[ATTR_LIMIT])
    )
    events: list[JsonValueType] = []
    for record in records:
        code = lookup(record.contact_id)
        event: dict[str, JsonValueType] = {
            "serial": record.serial,
            "code": record.contact_id,
            "description": code.description,
            "kind": code.kind.value,
            "subject": record.subject,
            "subject_kind": code.subject.value,
            "partition": record.partition,
            "timestamp": record.timestamp,
            "is_fence": record.is_fence,
        }
        if name := _subject_name(coordinator, record, code):
            event["subject_name"] = name
        events.append(event)
    return {
        # The cursor to resume from. Returned rather than left to the caller to compute, because
        # getting it wrong means either re-reading the whole buffer or silently skipping records.
        "next_serial": records[-1].serial
        if records
        else int(call.data[ATTR_SINCE_SERIAL]),
        "count": len(events),
        "events": events,
    }


def _subject_name(
    coordinator: JflPanelCoordinator, record: EventRecord, code: ContactIdCode
) -> str:
    """Resolve a buffered event's subject to a programmed name, on the same rules as the live one.

    `099` and `000` are origins — the monitoring connection and the mobile app — and a fence event
    carries `099` too, so none of them is looked up as a person. See `event._subject_name`.
    """
    if record.is_fence or record.subject in (0, 99):
        return ""
    if code.subject is EventSubject.USER:
        return coordinator.programming.user_name(record.subject)
    if code.subject is EventSubject.ZONE:
        return coordinator.programming.zone_name(record.subject)
    return ""


async def _read_programming(
    coordinator: JflPanelCoordinator, call: ServiceCall
) -> ServiceResponse:
    """Read the panel's programming and return what it says.

    A **read**, so it works in read-only mode. The response carries the zone and partition names,
    which is what most callers want it for — and **never a user access code**: the parser discards
    those, so this response cannot contain one.
    """
    programming = await coordinator.async_read_programming()
    zones: dict[str, JsonValueType] = {
        str(number): record.name for number, record in sorted(programming.zones.items())
    }
    partitions: dict[str, JsonValueType] = {
        str(number): record.name
        for number, record in sorted(programming.partitions.items())
    }
    users: list[JsonValueType] = [
        {"number": record.number, "name": record.name, "has_code": record.has_code}
        for record in sorted(
            programming.users.values(), key=lambda record: record.number
        )
        if record.name
    ]
    wireless: list[JsonValueType] = [
        {"slot": record.slot, "serial": record.serial, "zone": record.zone}
        for record in sorted(
            programming.wireless.values(), key=lambda record: record.slot
        )
        if record.present
    ]
    return {
        "checksum": programming.checksum.hex().upper(),
        "zones": zones,
        "partitions": partitions,
        "users": users,
        "wireless": wireless,
        "incomplete": list(programming.incomplete),
    }


@callback
def _coordinator_for(hass: HomeAssistant, call: ServiceCall) -> JflPanelCoordinator:
    """Resolve the target device to the coordinator of the panel it belongs to.

    A partition or fence sub-device resolves to its parent panel, because that is where the
    connection is — somebody targeting "Partition 1" to sync the clock means the panel it is on.
    """
    device_id = str(call.data[ATTR_DEVICE_ID])
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_device",
            translation_placeholders={"device_id": device_id},
        )

    serials = {
        identifier[1].split("-", 1)[0]
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    }
    for entry_id in device.config_entries:
        entry: JflConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
        # `runtime_data` only exists while the entry is loaded, and reaching for it on an unloaded
        # one raises rather than returning `None`.
        runtime: JflRuntimeData | None = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        for serial in serials:
            if serial in runtime.coordinators:
                return runtime.coordinators[serial]

    LOGGER.debug(
        "service call targeted device %s, which resolves to no loaded panel", device_id
    )
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_device",
        translation_placeholders={"device_id": device_id},
    )
