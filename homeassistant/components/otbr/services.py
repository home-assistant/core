"""Actions for the Open Thread Border Router integration."""

import logging
from typing import TYPE_CHECKING, Any

from python_otbr_api import PENDING_DATASET_DELAY_TIMER, OTBRError, tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType
import voluptuous as vol

from homeassistant.components.thread import (
    DatasetAddResult,
    async_add_dataset,
    async_get_preferred_dataset,
    async_get_store,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util

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

# How long the write itself can take: the library reads the pending dataset
# and then writes it, each bounded by the ten second timeout the integration
# gives its API client.
_WRITE_WINDOW_S = 20

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

SERVICE_MIGRATE_NETWORK_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_DATASET): cv.string,
        vol.Optional(ATTR_DELAY, default=DEFAULT_DELAY_S): vol.All(
            vol.Coerce(int), vol.Range(min=30, max=3600)
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
    comparison.
    """
    ignored = {
        MeshcopTLVType.ACTIVETIMESTAMP,
        MeshcopTLVType.PENDINGTIMESTAMP,
        MeshcopTLVType.DELAYTIMER,
    }
    return {k: v.data for k, v in active.items() if k not in ignored} == {
        k: v.data for k, v in target.items() if k not in ignored
    }


async def _async_repoint_preferred_dataset(
    hass: HomeAssistant, source_extended_pan_id: str, target_extended_pan_id: str
) -> None:
    """Move the preferred dataset along with a migration away from it.

    Everything that hands out Thread credentials (the config flow, HomeKit
    bridges, the Thread panel) starts from the preferred dataset. Leaving
    it on the abandoned network would keep sharing credentials no network
    runs any more - and this action's own no-dataset default would migrate
    a router back onto them.

    When no preference exists yet the target becomes it. The store picks a
    preference on its own when a router's first dataset arrives and it finds
    that router alone on its network, after a discovery wait; a migration
    started inside that wait would otherwise see the abandoned network
    chosen once it ends, with the same consequences.
    """
    store = await async_get_store(hass)
    source_id = None
    target_id = None
    # Two independent matches: a credential rotation keeps the network, so
    # source and target are the same entry and must both resolve to it.
    for entry in store.datasets.values():
        if entry.extended_pan_id.lower() == source_extended_pan_id.lower():
            source_id = entry.id
        if entry.extended_pan_id.lower() == target_extended_pan_id.lower():
            target_id = entry.id
    # With no source entry -- a router re-provisioned by another controller
    # runs a network the store never saw -- the promotion still applies:
    # the membership test then only matches a missing preference.
    if target_id and store.preferred_dataset in (source_id, None):
        store.preferred_dataset = target_id


async def _pinned_channel_of_another_router(
    hass: HomeAssistant,
    entry: OTBRConfigEntry,
    active: dict[MeshcopTLVType | int, tlv_parser.MeshcopTLVItem],
) -> int | None:
    """Return a channel another router on the same network is pinned to.

    Only routers that are actually pinned are asked which network they are
    on, so the common setup pays for no extra calls. A pinned router that
    cannot be read is an error rather than skipped: its REST API being down
    says nothing about its radio, which may still be on this mesh and would
    follow the pending dataset off the channel it shares with Zigbee.
    Configured entries count even when they are not loaded, for the same
    reason: a failed setup or an unload does not stop the radio.
    """
    source_xpan = active.get(MeshcopTLVType.EXTPANID)
    if source_xpan is None:
        return None

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
            raise ServiceValidationError(
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


async def _router_holds_a_pending_dataset(data: OTBRData) -> bool:
    """Return whether the router has a pending dataset, assuming it does.

    Asked after a write whose outcome the connection did not report. Any
    pending dataset means one is propagating, whether or not it is the one
    that was being written. A router that cannot be asked leaves the
    question open, and the answer that protects the mesh is that there is
    one.
    """
    try:
        return await data.get_pending_dataset_tlvs() is not None
    except HomeAssistantError:
        return True


async def _write_pending_dataset(
    data: OTBRData,
    dataset: bytes,
    issued: IssuedTimestamps,
    source_xpan: str | None,
    stamp: tuple[int, int],
    delay: int,
) -> None:
    """Hand the pending dataset to the router, recording it as propagating.

    The record is written before the write and deliberately outlasts the
    delay: the router starts its own timer only once it accepts the dataset,
    up to _WRITE_WINDOW_S later, and a crash in between leaves this record
    as the only one. Erring long costs a late retry after such a crash;
    erring short lets the next migration overtake a mesh still counting
    down. The record is tightened to the real deadline once the write
    completes.
    """
    previous = issued.record(source_xpan) if source_xpan is not None else None
    if source_xpan is not None:
        await issued.async_set(
            source_xpan,
            stamp,
            until=dt_util.utcnow().timestamp() + delay + _WRITE_WINDOW_S,
        )
    try:
        await data.set_pending_dataset_tlvs(dataset)
    except HomeAssistantError as err:
        if source_xpan is not None:
            # A definitive answer from the router, or the library's own
            # refusal, means nothing was written. A dropped connection
            # leaves that open, so ask the router: holding a pending
            # dataset means something is propagating and the window stays,
            # measured from the latest moment the write can have landed;
            # holding none means it never arrived, and keeping the window
            # would refuse every retry until it expired.
            if isinstance(
                err.__cause__, OTBRError
            ) or not await _router_holds_a_pending_dataset(data):
                await issued.async_restore(source_xpan, previous)
            else:
                await issued.async_set(
                    source_xpan, stamp, until=dt_util.utcnow().timestamp() + delay
                )
        raise
    if source_xpan is not None:
        # The router's delay timer started when it accepted the write, not
        # when the request left: a slow request would otherwise end the
        # recorded window while the mesh is still counting down.
        await issued.async_set(
            source_xpan, stamp, until=dt_util.utcnow().timestamp() + delay
        )


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
    delay: int = call.data[ATTR_DELAY]

    async with async_get_dataset_lock(call.hass):
        # Resolved under the lock: a queued no-dataset call must see the
        # preferred dataset as repointed by the migration it waited for,
        # or it would migrate the router straight back.
        dataset = await _target_dataset(call)

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

        active_tlvs = await data.get_active_dataset_tlvs()
        if active_tlvs is None:
            # An unprovisioned router has no network to migrate; joining one
            # is what the existing configuration flows are for.
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_active_network"
            )
        try:
            active = tlv_parser.parse_tlv(active_tlvs.hex())
        except tlv_parser.TLVError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="router_dataset_invalid"
            ) from err

        # A pending dataset in flight means the mesh is mid-change: a
        # migration or a channel change is propagating, and every device
        # holding that dataset is counting down towards it. Superseding it
        # would race those timers -- a late replacement splits the mesh --
        # and would silently undo the change the user may not even know is
        # queued. Refuse and say so; the library's own guard on the write
        # backstops the race where one appears after this read.
        if await data.get_pending_dataset_tlvs() is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pending_dataset_in_place"
            )

        # Only an identical dataset is a no-op. Comparing the extended PAN
        # ID alone would silently ignore a dataset that keeps the network
        # but replaces its credentials, which is how a network key is
        # rotated.
        if _same_network_settings(active, target):
            return {"status": "already_on_network"}

        # A different radio (like Zigbee in multiprotocol setups) may pin
        # the channel; refuse a migration that would move off it, as a
        # channel change does. The completeness check above guarantees the
        # target names its channel, so the guard cannot be skipped.
        channel_item = target[MeshcopTLVType.CHANNEL]
        if TYPE_CHECKING:
            assert isinstance(channel_item, tlv_parser.Channel)
        target_channel = channel_item.channel
        allowed_channel = await get_allowed_channel(call.hass, entry.data["url"])
        if allowed_channel is None:
            # The pending dataset reaches every router on the mesh, not only
            # the one it is handed to, so a router that shares its radio has
            # a say even when the migration is started through another.
            allowed_channel = await _pinned_channel_of_another_router(
                call.hass, entry, active
            )
        if allowed_channel and target_channel != allowed_channel:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="channel_conflict",
                translation_placeholders={
                    "target_channel": str(target_channel),
                    "allowed_channel": str(allowed_channel),
                },
            )

        # The pending dataset must carry timestamps newer than the network
        # being left: a not-newer pending dataset is silently ignored by
        # the mesh while this action would still report success.
        newest = max(
            _timestamp_parts(active, MeshcopTLVType.ACTIVETIMESTAMP),
            _timestamp_parts(target, MeshcopTLVType.ACTIVETIMESTAMP),
        )
        # The dataset store silently keeps an existing entry for the same
        # extended PAN ID unless the update is newer, so stamp above the
        # stored dataset too - or the mesh would migrate while the store
        # kept (and the preferred pointer shared) the old credentials.
        store = await async_get_store(call.hass)
        target_xpan = str(target[MeshcopTLVType.EXTPANID]).lower()
        for entry_ in store.datasets.values():
            if entry_.extended_pan_id.lower() == target_xpan:
                newest = max(
                    newest,
                    _timestamp_parts(entry_.dataset, MeshcopTLVType.ACTIVETIMESTAMP),
                )
        # A pending dataset takes its delay to propagate, so a second
        # migration of the same mesh -- another border router on it, moving to
        # a different network -- can still read the old active dataset and no
        # pending one, and would otherwise pick the same timestamp. Stamp
        # above what this integration has already handed out for this mesh.
        issued = await async_get_issued_timestamps(call.hass)
        source_xpan_item = active.get(MeshcopTLVType.EXTPANID)
        source_xpan = str(source_xpan_item).lower() if source_xpan_item else None
        if source_xpan is not None:
            # A newer stamp is not enough while the earlier dataset is still
            # propagating: a router that has not learned it yet accepts this
            # one in its place, and devices that only got the earlier dataset
            # end up on a different network than the rest. Refuse until the
            # earlier migration's delay has expired.
            if remaining := issued.seconds_in_flight(source_xpan):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="migration_in_flight",
                    translation_placeholders={"remaining": str(remaining)},
                )
            newest = max(newest, issued.get(source_xpan))

        # Always step the seconds, never the ticks: python_otbr_api's channel
        # change stamps seconds + 1 and ignores ticks, so a network left at the
        # last representable second would wrap that write to zero and have the
        # mesh ignore every later channel change.
        newest_seconds = newest[0]
        if newest_seconds >= 2**48 - 1:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="timestamp_exhausted"
            )
        seconds = newest_seconds + 1

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

        # Fetched before the write: a failure here must abort the action
        # before the mesh starts migrating, not after.
        border_agent_id = (await data.get_border_agent_id()).hex()
        extended_address = (await data.get_extended_address()).hex()

        if call.data.get(ATTR_DATASET) is None:
            # The target came from the preferred dataset, which another writer
            # can replace while the router is being read. Sending the snapshot
            # now would put credentials on the mesh that Home Assistant has
            # already superseded -- and stamped newer, so the newer ones would
            # be lost. Nothing has been written yet, so this can still refuse.
            preferred = await async_get_preferred_dataset(call.hass)
            if preferred is not None and bytes.fromhex(preferred) != dataset:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="preferred_dataset_changed",
                )

        await _write_pending_dataset(
            data,
            bytes.fromhex(tlv_parser.encode_tlv(pending)),
            issued,
            source_xpan,
            (seconds, 0),
            delay,
        )

        # What the network will run after the delay is the re-stamped
        # dataset; record it so Home Assistant's view of the network stays
        # current, bound to this router the same way setup binds datasets.
        del pending[MeshcopTLVType.PENDINGTIMESTAMP]
        del pending[MeshcopTLVType.DELAYTIMER]
        migrated_tlvs = bytes.fromhex(tlv_parser.encode_tlv(pending))
        result = await async_add_dataset(
            call.hass,
            DOMAIN,
            migrated_tlvs.hex(),
            preferred_border_agent_id=border_agent_id,
            preferred_extended_address=extended_address,
        )
        # The repair issues describe the credentials the network is adopting,
        # the same way the create and set-network paths report them.
        await update_issues(call.hass, data, migrated_tlvs)
        if source_xpan is not None:
            await _async_repoint_preferred_dataset(
                call.hass, source_xpan, str(target[MeshcopTLVType.EXTPANID])
            )
        # The store saves on a delay, and a normal restart flushes it; a crash
        # inside that delay would not. The mesh is migrating either way, so
        # write now: the dataset entry would be re-imported from the router
        # on the next setup, but the preferred pointer would stay on the
        # abandoned network until someone noticed.
        await store.async_save()
        if result is DatasetAddResult.DISCARDED:
            # Newer credentials for this network were stored while the router
            # was being written to. The mesh is migrating to the dataset above
            # and cannot be called back, so say so rather than report a success
            # Home Assistant cannot back up.
            #
            # Reported after the two calls above on purpose: they describe
            # which network is being adopted rather than with which
            # credentials, so they are right either way and must still run --
            # in particular the preferred pointer, which this action's own
            # default target reads.
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
