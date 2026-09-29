"""Actions for the Open Thread Border Router integration."""

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


async def _target_dataset(call: ServiceCall) -> bytes:
    """Return the dataset named by the call, or the preferred one."""
    # Presence, not truthiness: an empty dataset is a caller mistake (a
    # template that resolved to nothing), not a request for the default.
    if (dataset_hex := call.data.get(ATTR_DATASET)) is not None:
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
    preferred = await async_get_preferred_dataset(call.hass)
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

    The timestamps say when a dataset was made, not what it configures, and
    this one is re-stamped before it is sent, so they are left out of the
    comparison. Compared as the Thread dataset store compares them: the
    router adds a wake-up channel to a dataset without one and cannot keep
    the legacy Beacons flag, so a target differing only there is what the
    router already reports.
    """
    ignored = {
        MeshcopTLVType.ACTIVETIMESTAMP,
        MeshcopTLVType.PENDINGTIMESTAMP,
        MeshcopTLVType.DELAYTIMER,
    }
    return {
        k: v.data for k, v in normalize_dataset(active).items() if k not in ignored
    } == {k: v.data for k, v in normalize_dataset(target).items() if k not in ignored}


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
    """
    other: OTBRConfigEntry
    for other in hass.config_entries.async_loaded_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            continue
        try:
            other_tlvs = await other.runtime_data.get_active_dataset_tlvs()
            if other_tlvs is None:
                # Not on any mesh, so not on this one.
                continue
            other_active = tlv_parser.parse_tlv(other_tlvs.hex())
            other_xpan = other_active.get(MeshcopTLVType.EXTPANID)
            if other_xpan is None or str(other_xpan).lower() != source_extended_pan_id:
                continue
            await update_issues(hass, other.runtime_data, migrated_tlvs)
        except (HomeAssistantError, tlv_parser.TLVError) as err:
            _LOGGER.debug(
                "Could not refresh the repair issues of %s: %s", other.title, err
            )


async def _pinned_channel_of_another_router(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
) -> int | None:
    """Return a channel another router on the same network is pinned to.

    Only routers that are actually pinned are asked which network they are
    on, so the common setup pays for no extra calls. A pinned router that
    cannot be read is a failure rather than skipped: its REST API being down
    says nothing about its radio, which may still be on this mesh and would
    follow the pending dataset off the channel it shares with Zigbee.
    Configured entries count even when they are not loaded, for the same
    reason: a failed setup or an unload does not stop the radio, and is the
    caller's to fix, so that one is a validation error.
    """
    source_xpan = active[MeshcopTLVType.EXTPANID]

    other: OTBRConfigEntry
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            continue
        # An ignored discovery has no URL to judge; nothing to check.
        if (url := other.data.get("url")) is None:
            continue
        pinned = await get_allowed_channel(hass, url)
        if pinned is None:
            continue
        # Not loaded means it cannot be asked which network it is on;
        # fail safe, exactly like a router whose read fails below.
        if other.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="pinned_router_unreachable",
                translation_placeholders={"router": other.title},
            )
        try:
            other_tlvs = await other.runtime_data.get_active_dataset_tlvs()
            other_active = (
                tlv_parser.parse_tlv(other_tlvs.hex())
                if other_tlvs is not None
                else None
            )
        except (HomeAssistantError, tlv_parser.TLVError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pinned_router_unreachable",
                translation_placeholders={"router": other.title},
            ) from err
        # No active dataset: the router is not on any mesh.
        if other_active is None:
            continue
        if other_active.get(MeshcopTLVType.EXTPANID) == source_xpan:
            return pinned

    return None


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


async def _async_active_dataset(
    data: OTBRData,
) -> tuple[dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem], str]:
    """Return the router's active dataset and the extended PAN ID it names.

    Everything that keeps a migration safe is keyed by that network: the
    stamps handed out for it, the window its pending dataset propagates in,
    the preferred pointer moving off it. OpenThread does not count a router
    as commissioned without one, so a dataset lacking it is refused.
    """
    active_tlvs = await data.get_active_dataset_tlvs()
    if active_tlvs is None:
        # An unprovisioned router has no network to migrate; joining one is
        # what the configuration flows are for.
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_active_network"
        )
    try:
        active = tlv_parser.parse_tlv(active_tlvs.hex())
    except tlv_parser.TLVError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="router_dataset_invalid"
        ) from err
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
    """Refuse a migration off a channel another radio pins.

    A channel change refuses the same. The pending dataset reaches every
    router on the mesh, so a router that shares its radio has a say even
    when the migration is started through another.
    """
    channel_item = target[MeshcopTLVType.CHANNEL]
    if TYPE_CHECKING:
        assert isinstance(channel_item, tlv_parser.Channel)
    target_channel = channel_item.channel
    allowed_channel = await get_allowed_channel(hass, entry.data["url"])
    if allowed_channel is None:
        allowed_channel = await _pinned_channel_of_another_router(hass, entry, active)
    if allowed_channel and target_channel != allowed_channel:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="channel_conflict",
            translation_placeholders={
                "target_channel": str(target_channel),
                "allowed_channel": str(allowed_channel),
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
    ignores the dataset; above the store's entry for the target, or the
    store keeps the old credentials while the mesh migrates; and above what
    this integration already handed out for the mesh, since a second router
    on it can still read the old active dataset and no pending one.
    """
    newest = max(
        _timestamp_parts(active, MeshcopTLVType.ACTIVETIMESTAMP),
        _timestamp_parts(target, MeshcopTLVType.ACTIVETIMESTAMP),
    )
    store = await async_get_store(hass)
    target_xpan = str(target[MeshcopTLVType.EXTPANID]).lower()
    for entry in store.datasets.values():
        if entry.extended_pan_id.lower() == target_xpan:
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


async def _async_migrate_network(call: ServiceCall) -> dict[str, Any]:
    """Migrate a border router and every device on its network.

    The target dataset is re-stamped newer than the network being left, so
    it wins dataset propagation, and handed to the router as a pending
    dataset with a delay. The router spreads it; the network switches as
    one when the delay expires. The checks run in an order that matters;
    each says why.
    """
    entry: OTBRConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY)
    )
    data = entry.runtime_data

    async with async_get_dataset_lock(call.hass):
        # Resolved under the lock: a queued no-dataset call must see the
        # preferred dataset as repointed by the migration it waited for,
        # or it would migrate the router straight back.
        dataset = await _target_dataset(call)
        target = _parse_target(dataset)
        active, source_xpan = await _async_active_dataset(data)

        # A pending dataset in flight means the mesh is mid-change, every
        # device counting down towards it. Superseding it would race those
        # timers and silently undo a change the user may not know is queued.
        # The library's own guard on the write backstops the race where one
        # appears after this read.
        if await data.get_pending_dataset_tlvs() is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pending_dataset_in_place"
            )

        delay = _effective_delay(active, target, call.data[ATTR_DELAY])

        # A newer stamp is not enough while an earlier dataset issued for
        # this mesh is still propagating: a router that has not learned it
        # yet accepts this one in its place, and devices that only got the
        # earlier dataset end up on a different network than the rest.
        issued = await async_get_issued_timestamps(call.hass)
        if remaining := issued.seconds_in_flight(source_xpan):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="migration_in_flight",
                translation_placeholders={"remaining": str(remaining)},
            )

        # Only an identical dataset is a no-op: a dataset that keeps the
        # network but replaces its credentials is how a key is rotated.
        # Checked after the window above, since this router can still report
        # an active dataset the mesh is already leaving.
        if _same_network_settings(active, target):
            return {"status": "already_on_network"}

        await _async_check_channel(call.hass, entry, active, target)

        seconds = await _async_next_seconds(
            call.hass, active, target, issued, source_xpan
        )
        pending = _pending_dataset(target, seconds, delay)

        # Fetched before the write: a failure here must abort the action
        # before the mesh starts migrating, not after.
        border_agent_id = (await data.get_border_agent_id()).hex()
        extended_address = (await data.get_extended_address()).hex()

        if call.data.get(ATTR_DATASET) is None:
            # The target came from the preferred dataset, which another writer
            # can replace while the router is being read. Sending the snapshot
            # would put credentials on the mesh that Home Assistant has already
            # superseded -- stamped newer, so the newer ones would be lost.
            preferred = await async_get_preferred_dataset(call.hass)
            if preferred is not None and bytes.fromhex(preferred) != dataset:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="preferred_dataset_changed",
                )

        pending_tlvs = bytes.fromhex(tlv_parser.encode_tlv(pending))
        await issued.async_write(
            data,
            source_xpan,
            (seconds, 0),
            delay,
            lambda: data.set_pending_dataset_tlvs(pending_tlvs),
        )

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

    # With the lock released: refreshing the other routers' repair issues
    # reads each of them, up to a timeout apiece, and no other dataset writer
    # should queue behind that.
    await update_issues(call.hass, data, migrated_tlvs)
    await _async_refresh_issues_on_the_mesh(
        call.hass, entry, source_xpan, migrated_tlvs
    )
    if result is DatasetAddResult.DISCARDED:
        # Newer credentials for this network were stored while the router
        # was being written to. The mesh is migrating to the dataset above
        # and cannot be called back, so say so rather than report a success
        # Home Assistant cannot back up. Raised after the bookkeeping above
        # on purpose: that describes which network is being adopted, which
        # is right either way, and this action's own default target reads
        # the preferred pointer.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="dataset_discarded"
        )

    name_item = pending[MeshcopTLVType.NETWORKNAME]
    if TYPE_CHECKING:
        assert isinstance(name_item, tlv_parser.NetworkName)
    return {
        "status": "migrating",
        "delay": delay,
        "network_name": name_item.name,
    }


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
