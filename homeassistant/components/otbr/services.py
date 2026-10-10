"""Actions for the Open Thread Border Router integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

import probatio
from python_otbr_api import PENDING_DATASET_DELAY_TIMER, tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.thread import (
    DatasetAddResult,
    async_add_dataset,
    async_get_preferred_dataset,
    async_get_store,
    normalize_dataset,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .util import (
    async_get_dataset_lock,
    async_get_issued_timestamps,
    get_allowed_channel,
    parse_dataset,
    update_issues,
)

if TYPE_CHECKING:
    from .types import OTBRConfigEntry
    from .util import IssuedTimestamps, OTBRData

_LOGGER = logging.getLogger(__name__)

SERVICE_MIGRATE_NETWORK = "migrate_network"

ATTR_CONFIG_ENTRY = "config_entry"
ATTR_DATASET = "dataset"
ATTR_DELAY = "delay"

# The delay recommended for a channel change; a network change needs the
# same grace for sleepy devices to hear about it.
DEFAULT_DELAY_S = PENDING_DATASET_DELAY_TIMER // 1000

# What the Thread leader will accept. It raises anything shorter than its
# default delay when the dataset changes the network key, and anything
# below its minimum otherwise (OPENTHREAD_CONFIG_TMF_PENDING_DATASET_-
# DEFAULT_DELAY and _MINIMUM_DELAY).
_LEADER_KEY_CHANGE_DELAY_S = 300
_LEADER_MINIMUM_DELAY_S = 30

# The pending dataset is merged by the router over a base it chooses: an
# in-flight pending dataset, or a freshly generated random network. Any
# field left out here would come from that base, so a partial dataset
# would migrate the mesh onto settings nobody picked. Require the full
# set of network-defining fields instead.
_REQUIRED_DATASET_TLVS = (
    MeshcopTLVType.CHANNEL,
    MeshcopTLVType.CHANNELMASK,
    MeshcopTLVType.EXTPANID,
    MeshcopTLVType.MESHLOCALPREFIX,
    MeshcopTLVType.NETWORKKEY,
    MeshcopTLVType.NETWORKNAME,
    MeshcopTLVType.PANID,
    MeshcopTLVType.PSKC,
    MeshcopTLVType.SECURITYPOLICY,
)

# The components of an operational dataset, which is all OpenThread keeps
# of a dataset handed to it.
_OPERATIONAL_TLVS = frozenset(
    {
        MeshcopTLVType.ACTIVETIMESTAMP,
        MeshcopTLVType.CHANNEL,
        MeshcopTLVType.CHANNELMASK,
        MeshcopTLVType.DELAYTIMER,
        MeshcopTLVType.EXTPANID,
        MeshcopTLVType.MESHLOCALPREFIX,
        MeshcopTLVType.NETWORKKEY,
        MeshcopTLVType.NETWORKNAME,
        MeshcopTLVType.PANID,
        MeshcopTLVType.PENDINGTIMESTAMP,
        MeshcopTLVType.PSKC,
        MeshcopTLVType.SECURITYPOLICY,
        MeshcopTLVType.WAKEUP_CHANNEL,
    }
)

SERVICE_MIGRATE_NETWORK_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Optional(ATTR_DATASET): cv.string,
        probatio.Optional(ATTR_DELAY, default=DEFAULT_DELAY_S): probatio.All(
            probatio.Coerce(int), probatio.Range(min=30, max=3600)
        ),
    }
)


def _timestamp_parts(
    entries: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    tag: MeshcopTLVType,
) -> tuple[int, int]:
    """Return the (seconds, ticks) of the timestamp under tag, (0, 0) when absent.

    Thread orders timestamps by the pair, and so does the dataset store, so
    comparing seconds alone would miss a dataset that is newer by ticks.
    """
    item = entries.get(tag)
    if isinstance(item, tlv_parser.Timestamp):
        return (item.seconds, item.ticks)
    return (0, 0)


def _given_dataset(call: ServiceCall) -> bytes | None:
    """Return the dataset named by the call, None when it leaves the default."""
    # Presence, not truthiness: an empty dataset is a caller mistake (a
    # template that resolved to nothing), not a request for the default.
    if (dataset_hex := call.data.get(ATTR_DATASET)) is None:
        return None
    try:
        dataset = bytes.fromhex(dataset_hex)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_dataset"
        ) from err
    if dataset:
        return dataset
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="invalid_dataset"
    )


async def _preferred_dataset(hass: HomeAssistant) -> bytes:
    """Return the preferred dataset, the default target."""
    preferred = await async_get_preferred_dataset(hass)
    if preferred is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_preferred_dataset"
        )
    return bytes.fromhex(preferred)


def _same_network_settings(
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    target: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
) -> bool:
    """Return whether both datasets describe the same network settings.

    Only the operational components count: a dataset from the store or the
    router can carry TLVs the target was stripped of. The timestamps say when
    a dataset was made, not what it configures, and this one is re-stamped
    before it is sent, so they are left out too. Compared as the Thread
    dataset store compares them: the router adds a wake-up channel to a
    dataset without one and cannot keep the legacy Beacons flag, so a target
    differing only there is what the router already reports.
    """
    compared = _OPERATIONAL_TLVS - {
        MeshcopTLVType.ACTIVETIMESTAMP,
        MeshcopTLVType.PENDINGTIMESTAMP,
        MeshcopTLVType.DELAYTIMER,
    }
    return {
        k: v.data for k, v in normalize_dataset(active).items() if k in compared
    } == {k: v.data for k, v in normalize_dataset(target).items() if k in compared}


async def _async_preferred_replaced(call: ServiceCall, dataset: bytes) -> bool:
    """Return whether a default target no longer matches the preferred dataset."""
    if call.data.get(ATTR_DATASET) is not None:
        return False
    preferred = await async_get_preferred_dataset(call.hass)
    return preferred is not None and bytes.fromhex(preferred) != dataset


async def _async_repoint_preferred_dataset(
    hass: HomeAssistant, source_extended_pan_id: str, target_extended_pan_id: str
) -> None:
    """Move the preferred dataset along with a migration away from it.

    Everything that hands out Thread credentials (the config flow, HomeKit
    bridges, the Thread panel) starts from the preferred dataset. Leaving
    it on the abandoned network would keep sharing credentials no network
    runs any more - and this action's own no-dataset default would migrate
    a router back onto them.

    With no preference yet, the target becomes it: the network just chosen
    on purpose. The store only picks a preference itself for a router found
    alone on its network, after a discovery wait, and would settle on the
    abandoned network if that wait ended after the migration.
    """
    store = await async_get_store(hass)
    target_id = next(
        (
            entry.id
            for entry in store.datasets.values()
            if entry.extended_pan_id.lower() == target_extended_pan_id.lower()
        ),
        None,
    )
    if target_id is None:
        return
    # Judged by the network the pointer names: a credential rotation keeps
    # the network, so source and target are then the same entry.
    if (preferred := await async_get_preferred_dataset(hass)) is not None:
        preferred_xpan = tlv_parser.parse_tlv(preferred).get(MeshcopTLVType.EXTPANID)
        if str(preferred_xpan).lower() != source_extended_pan_id:
            return
    store.preferred_dataset = target_id


async def _async_refresh_issues_on_the_mesh(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    source_extended_pan_id: str,
    migrated_tlvs: bytes,
) -> None:
    """Update the repair issues of the other routers the migration reaches.

    The pending dataset reaches every border router on the mesh, so the
    issues raised against the network being left -- insecure credentials, a
    channel another radio is pinned to -- are as stale on the others as on
    the router the action was handed to. They are otherwise only recomputed
    when an entry is set up again.

    A router that cannot be read is skipped rather than raising: the mesh is
    migrating and cannot be called back, and its issues are recomputed at its
    next setup anyway. That is also why this runs last.

    A router that already reports the migrated network -- the delay can run
    out while the routers are read -- is refreshed from its own active
    dataset rather than skipped with the issues of the network it left.
    """
    migrated_xpan = str(
        tlv_parser.parse_tlv(migrated_tlvs.hex())[MeshcopTLVType.EXTPANID]
    ).lower()
    # Read at once: each read can wait out a timeout, and they are independent.
    # The runtime data is taken here, while each entry is known to be loaded.
    await asyncio.gather(
        *(
            _async_refresh_issues_of(
                hass,
                other.title,
                other.runtime_data,
                source_extended_pan_id,
                migrated_xpan,
                migrated_tlvs,
            )
            for other in hass.config_entries.async_loaded_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        )
    )


async def _async_refresh_issues_of(
    hass: HomeAssistant,
    title: str,
    other: OTBRData,
    source_extended_pan_id: str,
    migrated_xpan: str,
    migrated_tlvs: bytes,
) -> None:
    """Refresh one other router's repair issues, if the migration reaches it."""
    try:
        read = await _async_read_active_dataset(other)
    except HomeAssistantError as err:
        _LOGGER.debug("Could not refresh the repair issues of %s: %s", title, err)
        return
    if read is None:
        # Not on any mesh, so not on this one.
        return
    other_tlvs, other_active = read
    if (other_xpan := other_active.get(MeshcopTLVType.EXTPANID)) is None:
        return
    if str(other_xpan).lower() == source_extended_pan_id:
        await update_issues(hass, other, migrated_tlvs)
    elif str(other_xpan).lower() == migrated_xpan:
        await update_issues(hass, other, other_tlvs)


async def _pinned_channels_of_other_routers(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    target_channel: int,
) -> set[int]:
    """Return the channels other routers on the same network are pinned to.

    Only routers pinned to another channel than the target are asked which
    network they are on: a pin the target meets is no obstacle on any mesh,
    and the common setup pays for no extra calls. A pinned router that
    cannot be read is a failure rather than skipped: its REST API being down
    says nothing about its radio, which may still be on this mesh and would
    follow the pending dataset off the channel it shares with Zigbee.
    Configured entries count even when they are not loaded, for the same
    reason: a failed setup or an unload does not stop the radio, and is the
    caller's to fix, so that one is a validation error.
    """
    source_xpan = active[MeshcopTLVType.EXTPANID]
    pins: set[int] = set()

    other: OTBRConfigEntry
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            continue
        # An ignored discovery has no URL to judge; nothing to check.
        if (url := other.data.get("url")) is None:
            continue
        pinned = await get_allowed_channel(hass, url)
        if pinned is None or pinned == target_channel:
            continue
        # Not loaded means it cannot be asked which network it is on;
        # fail safe, exactly like a router whose read fails below.
        if other.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="pinned_router_not_loaded",
                translation_placeholders={"router": other.title},
            )
        try:
            read = await _async_read_active_dataset(other.runtime_data)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pinned_router_unreachable",
                translation_placeholders={"router": other.title},
            ) from err
        # No active dataset: the router is not on any mesh.
        if read is None:
            continue
        _, other_active = read
        # A dataset that names no network says nothing about which mesh the
        # radio is on; treated like a router that could not be read.
        if (other_xpan := other_active.get(MeshcopTLVType.EXTPANID)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pinned_router_unreachable",
                translation_placeholders={"router": other.title},
            )
        if other_xpan == source_xpan:
            pins.add(pinned)

    return pins


def _parse_target(
    dataset: bytes,
) -> dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]:
    """Return the target's operational TLVs, refusing an incomplete dataset."""
    try:
        target = tlv_parser.parse_tlv(dataset.hex())
    except tlv_parser.TLVError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_dataset"
        ) from err
    if missing := [tag.name for tag in _REQUIRED_DATASET_TLVS if tag not in target]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="incomplete_dataset",
            translation_placeholders={"missing": ", ".join(missing)},
        )
    # The router drops anything else, so what is sent and stored must not
    # carry it either: the store would otherwise disagree with the router's
    # copy at every setup and discard it.
    return {tag: item for tag, item in target.items() if tag in _OPERATIONAL_TLVS}


async def _async_read_active_dataset(
    data: OTBRData,
) -> tuple[bytes, dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]] | None:
    """Return a router's active dataset, raw and parsed, or None without one."""
    tlvs = await data.get_active_dataset_tlvs()
    return None if tlvs is None else (tlvs, parse_dataset(tlvs))


async def _async_active_dataset(
    data: OTBRData,
) -> tuple[dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], str]:
    """Return the router's active dataset and the extended PAN ID it names.

    Everything that keeps a migration safe is keyed by that network: the
    stamps handed out for it, the window its pending dataset propagates in,
    the preferred pointer moving off it. OpenThread does not count a router
    as commissioned without one, so a dataset lacking it is refused.
    """
    read = await _async_read_active_dataset(data)
    if read is None:
        # An unprovisioned router has no network to migrate; joining one is
        # what the configuration flows are for.
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_active_network"
        )
    _, active = read
    if (source_xpan := active.get(MeshcopTLVType.EXTPANID)) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="router_dataset_invalid"
        )
    return active, str(source_xpan).lower()


def _effective_delay(
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    target: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    delay: int,
) -> int:
    """Return the delay the mesh will actually use.

    The leader raises a delay it considers too short, but only on the copy it
    hands back: a router that writes the dataset locally keeps counting down
    from the value written to it, and nobody reports the raised value. So
    the window recorded and the delay reported would otherwise describe a
    migration still running; send what the leader will use instead.
    """
    if active.get(MeshcopTLVType.NETWORKKEY) != target[MeshcopTLVType.NETWORKKEY]:
        return max(delay, _LEADER_KEY_CHANGE_DELAY_S)
    return max(delay, _LEADER_MINIMUM_DELAY_S)


async def _async_check_channel(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    target: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
) -> None:
    """Refuse a migration off a channel a radio on the mesh pins.

    A channel change refuses the same. The pending dataset reaches every
    router on the mesh, so every router that shares its radio has a say,
    this one included; two pinned to different channels cannot both be
    served. This router's pin is a local lookup and refuses on its own; the
    others are read only once it is met.
    """
    channel_item = target[MeshcopTLVType.CHANNEL]
    if TYPE_CHECKING:
        assert isinstance(channel_item, tlv_parser.Channel)
    target_channel = channel_item.channel
    own = await get_allowed_channel(hass, entry.data["url"])
    missed = {own} if own is not None and own != target_channel else set()
    if not missed:
        missed = await _pinned_channels_of_other_routers(
            hass, entry, active, target_channel
        )
    if missed:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="channel_conflict",
            translation_placeholders={
                "target_channel": str(target_channel),
                "allowed_channel": ", ".join(str(pin) for pin in sorted(missed)),
            },
        )


async def _async_next_seconds(
    hass: HomeAssistant,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    target: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    issued: IssuedTimestamps,
    source_xpan: str,
) -> int:
    """Return the seconds to stamp the pending dataset with.

    Above the network being left and the target, or the mesh silently
    ignores the dataset; above the store's entries for both, since the store
    can know the network being left newer than this router does, and stamped
    below the target's entry the store keeps the old credentials while the
    mesh migrates; and above what this integration already handed out for the
    mesh, since a second router on it can still read the old active dataset
    and no pending one.
    """
    newest = max(
        _timestamp_parts(active, MeshcopTLVType.ACTIVETIMESTAMP),
        _timestamp_parts(target, MeshcopTLVType.ACTIVETIMESTAMP),
    )
    store = await async_get_store(hass)
    xpans = {source_xpan, str(target[MeshcopTLVType.EXTPANID]).lower()}
    for entry in store.datasets.values():
        if entry.extended_pan_id.lower() in xpans:
            newest = max(
                newest, _timestamp_parts(entry.dataset, MeshcopTLVType.ACTIVETIMESTAMP)
            )
    newest = max(newest, issued.get(source_xpan))

    # Always step the seconds, never the ticks: python_otbr_api's channel
    # change stamps seconds + 1 and ignores ticks. A stamp that cannot be
    # stepped is an error, not a wrap to zero the mesh would ignore.
    if newest[0] >= 2**48 - 1:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="timestamp_exhausted"
        )
    return newest[0] + 1


def _pending_dataset(
    target: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    seconds: int,
    delay: int,
) -> dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]:
    """Return the target stamped as the pending dataset to write."""
    pending = dict(target)
    pending[MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=seconds
    )
    pending[MeshcopTLVType.PENDINGTIMESTAMP] = tlv_parser.Timestamp.from_values(
        MeshcopTLVType.PENDINGTIMESTAMP, seconds=seconds
    )
    pending[MeshcopTLVType.DELAYTIMER] = tlv_parser.DelayTimer.from_milliseconds(
        delay * 1000
    )
    return pending


@dataclass(frozen=True, slots=True)
class _Landed:
    """A migration that landed on the router, reported on once the lock is released.

    `superseded` says the preferred dataset it was taken from changed while the
    router was being written to.
    """

    left: str
    tlvs: bytes
    result: DatasetAddResult
    superseded: bool = False


async def _async_finish_unanswered_migration(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    data: OTBRData,
    issued: IssuedTimestamps,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    extended_pan_id: str,
) -> _Landed | None:
    """Record a migration whose answer was lost, now the router is on its target.

    A write the router never answered keeps the window but records nothing
    else, since nothing may have been written. The router it was handed to
    reporting the network it moved to, stamped at or above what it was sent,
    settles it: store what it runs and move the preferred pointer, before a
    default target is read from a pointer still naming the network left. An
    unanswered change of the network's own settings is kept and settled the
    same way, the network being its own target.
    """
    left = issued.migration_source(extended_pan_id, entry.entry_id)
    if left is None or (sent := issued.sent(left)) is None:
        return None
    if _timestamp_parts(active, MeshcopTLVType.ACTIVETIMESTAMP) < _timestamp_parts(
        tlv_parser.parse_tlv(sent), MeshcopTLVType.ACTIVETIMESTAMP
    ):
        # Below what was sent: a rotation keeps the name; this router stayed.
        return None
    border_agent_id = (await data.get_border_agent_id()).hex()
    extended_address = (await data.get_extended_address()).hex()
    tlvs = bytes.fromhex(tlv_parser.encode_tlv(active))
    result = await _async_record_migration(
        hass, left, extended_pan_id, tlvs, border_agent_id, extended_address
    )
    await issued.async_confirm(left)
    return _Landed(left, tlvs, result)


async def async_settle_unanswered_migration(
    hass: HomeAssistant, entry: OTBRConfigEntry, data: OTBRData, active_tlvs: bytes
) -> None:
    """Settle a migration this router never answered, at the router's setup.

    A restart inside the delay leaves the record as the only trace of the
    migration. The router found on the target when it is set up again settles
    it as the action would, so the preferred pointer does not stay on the
    network left until the action is run again. The caller holds the dataset
    lock. A dataset the store kept a newer one over is logged: setup has
    nobody to report it to.
    """
    try:
        active = parse_dataset(active_tlvs)
    except HomeAssistantError:
        # Left to the import that follows, which reports it.
        return
    if (extended_pan_id := active.get(MeshcopTLVType.EXTPANID)) is None:
        return
    issued = await async_get_issued_timestamps(hass)
    landed = await _async_finish_unanswered_migration(
        hass, entry, data, issued, active, str(extended_pan_id).lower()
    )
    if landed is not None and landed.result is DatasetAddResult.DISCARDED:
        _LOGGER.warning(
            "The migration %s was handed to has landed, but Home Assistant kept "
            "newer credentials for the network %s; check the Thread panel",
            entry.title,
            str(extended_pan_id).lower(),
        )


async def _async_record_migration(
    hass: HomeAssistant,
    source_xpan: str,
    target_xpan: str,
    migrated_tlvs: bytes,
    border_agent_id: str,
    extended_address: str,
) -> DatasetAddResult:
    """Store the migrated dataset, move the preferred pointer, flush the store.

    Flushed now rather than on the store's save delay: the mesh is migrating
    either way, and a crash inside the delay would re-import the dataset from
    the router at the next setup but leave the preferred pointer on the
    abandoned network.
    """
    result = await async_add_dataset(
        hass,
        DOMAIN,
        migrated_tlvs.hex(),
        preferred_border_agent_id=border_agent_id,
        preferred_extended_address=extended_address,
    )
    await _async_repoint_preferred_dataset(hass, source_xpan, target_xpan)
    store = await async_get_store(hass)
    await store.async_save()
    return result


async def _async_migrate_under_lock(
    call: ServiceCall,
    entry: OTBRConfigEntry,
    data: OTBRData,
    issued: IssuedTimestamps,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
    source_xpan: str,
    given: tuple[bytes, dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]] | None,
) -> tuple[dict[str, Any], _Landed | None]:
    """Run the migration's checks and its write, in the order that protects the mesh.

    Each check says why it comes where it does. Returns the action's response
    and the migration recorded, if one was written.
    """
    if given is None:
        # Resolved here, not before the lock: a queued call without a dataset
        # must see the preferred pointer as moved by the migration it waited
        # for, or by the one settled above, or it would migrate straight back.
        dataset = await _preferred_dataset(call.hass)
        target = _parse_target(dataset)
    else:
        dataset, target = given

    delay = _effective_delay(active, target, call.data[ATTR_DELAY])
    target_xpan = str(target[MeshcopTLVType.EXTPANID]).lower()

    # A router that has not learned the dataset in flight yet would take
    # this one instead, and a mesh on its way here was sent this network.
    if remaining := issued.seconds_in_flight(source_xpan):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="migration_in_flight",
            translation_placeholders={"remaining": str(remaining)},
        )

    # Nor onto a network whose own mesh is counting down: this one would
    # arrive after the others have left, or on their old channel.
    if remaining := issued.seconds_propagating(target_xpan):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="target_in_flight",
            translation_placeholders={"remaining": str(remaining)},
        )

    # A known network is migrated to as known, stored or sent in an unrecorded
    # migration, or two meshes of one identity arise; a rotation is exempt.
    if source_xpan != target_xpan:
        store = await async_get_store(call.hass)
        known = [
            entry.dataset
            for entry in store.datasets.values()
            if entry.extended_pan_id.lower() == target_xpan
        ]
        known.extend(
            tlv_parser.parse_tlv(sent) for sent in issued.attempted(target_xpan)
        )
        if any(not _same_network_settings(held, target) for held in known):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="target_settings_differ"
            )

    # Only an identical dataset is a no-op; one keeping the network with new
    # credentials is a rotation. After the windows: this router can still
    # report an active dataset the mesh is leaving.
    if _same_network_settings(active, target):
        return {"status": "already_on_network"}, None

    await _async_check_channel(call.hass, entry, active, target)

    seconds = await _async_next_seconds(call.hass, active, target, issued, source_xpan)
    pending = _pending_dataset(target, seconds, delay)

    # Fetched before the write: a failure must abort before the mesh moves.
    border_agent_id = (await data.get_border_agent_id()).hex()
    extended_address = (await data.get_extended_address()).hex()

    # The store takes no lock, so the preferred dataset can change while the
    # router is read. Refused while nothing has been sent yet.
    if await _async_preferred_replaced(call, dataset):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="preferred_dataset_changed"
        )

    pending_tlvs = bytes.fromhex(tlv_parser.encode_tlv(pending))
    await issued.async_write(
        data,
        source_xpan,
        (seconds, 0),
        delay,
        lambda: data.set_pending_dataset_tlvs(pending_tlvs),
        migration=(target_xpan, entry.entry_id, pending_tlvs.hex()),
    )

    # Replaced during the write, the mesh migrates to the snapshot anyway;
    # reported after the bookkeeping, like a discarded store write.
    superseded = await _async_preferred_replaced(call, dataset)

    # What the network will run after the delay is the re-stamped
    # dataset, bound to this router the same way setup binds datasets.
    del pending[MeshcopTLVType.PENDINGTIMESTAMP]
    del pending[MeshcopTLVType.DELAYTIMER]
    migrated_tlvs = bytes.fromhex(tlv_parser.encode_tlv(pending))
    result = await _async_record_migration(
        call.hass,
        source_xpan,
        str(target[MeshcopTLVType.EXTPANID]),
        migrated_tlvs,
        border_agent_id,
        extended_address,
    )
    await issued.async_confirm(source_xpan)

    name_item = pending[MeshcopTLVType.NETWORKNAME]
    if TYPE_CHECKING:
        assert isinstance(name_item, tlv_parser.NetworkName)
    return {
        "status": "migrating",
        "delay": delay,
        "network_name": name_item.name,
    }, _Landed(source_xpan, migrated_tlvs, result, superseded)


async def _async_migrate_network(call: ServiceCall) -> dict[str, Any]:
    """Migrate a border router and every device on its network.

    The target dataset is re-stamped newer than the network being left, so
    it wins dataset propagation, and handed to the router as a pending
    dataset with a delay. The router spreads it; the network switches as
    one when the delay expires.
    """
    entry: OTBRConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY)
    )
    data = entry.runtime_data

    # A dataset given is checked before the router is read: one that does not
    # describe a network touches nothing. The default target is resolved
    # under the lock instead, since the preferred pointer may move there.
    given = None
    if (dataset := _given_dataset(call)) is not None:
        given = (dataset, _parse_target(dataset))

    async with async_get_dataset_lock(call.hass):
        # A pending dataset has every device counting down to it; superseding
        # it would undo a change the user may not know is queued. Read before
        # the network is, so an active dataset read after a pending one has
        # expired is the network as it is now. The library's own guard on the
        # write covers one that appears after this read.
        if await data.get_pending_dataset_tlvs() is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pending_dataset_in_place"
            )
        active, source_xpan = await _async_active_dataset(data)
        issued = await async_get_issued_timestamps(call.hass)
        finished = await _async_finish_unanswered_migration(
            call.hass, entry, data, issued, active, source_xpan
        )
        discarded = (
            finished is not None and finished.result is DatasetAddResult.DISCARDED
        )
        response: dict[str, Any] | None = None
        migration: _Landed | None = None
        failure: HomeAssistantError | None = None
        # A discarded recovery writes nothing more: the mesh runs credentials
        # the store has already superseded, which is reported below.
        if not discarded:
            try:
                response, migration = await _async_migrate_under_lock(
                    call, entry, data, issued, active, source_xpan, given
                )
            except HomeAssistantError as err:
                # Raised after the migration settled above is reported on:
                # its record is gone, so no later call would refresh for it.
                failure = err

    # Outside the lock: the other routers are read, up to a timeout apiece,
    # and no dataset writer should queue behind that.
    recorded = [done for done in (finished, migration) if done is not None]
    for done in recorded:
        await update_issues(call.hass, data, done.tlvs)
        await _async_refresh_issues_on_the_mesh(call.hass, entry, done.left, done.tlvs)
    if failure is not None:
        raise failure
    if migration is not None and migration.superseded:
        # Reported after the bookkeeping, like the discarded write below.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="preferred_dataset_superseded"
        )
    if any(done.result is DatasetAddResult.DISCARDED for done in recorded):
        # The mesh is migrating to credentials the store has since replaced
        # and cannot be called back: reported, rather than as a success Home
        # Assistant cannot back up, once the bookkeeping is done.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="dataset_discarded"
        )
    if TYPE_CHECKING:
        assert response is not None
    return response


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions of the integration."""
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_MIGRATE_NETWORK,
        _async_migrate_network,
        schema=SERVICE_MIGRATE_NETWORK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
