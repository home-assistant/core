"""Derive the group addresses equivalent channels use.

Format neutral core of the "existing configuration" suggestions: it works
purely on parsed ETS project data and on group addresses, so it knows nothing
about how a caller stores its entity configuration.

Given the group addresses of a configured entity it locates the device channel
they belong to, and reports for every other channel of that device - and of
identically programmed devices - which addresses take their place. A caller
maps that back onto its own configuration format.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from xknxproject.models import CommunicationObject, KNXProject

type GaSlot = Literal["write", "state"]


@dataclass(frozen=True)
class SourceAddress:
    """A group address of an existing configuration with its role."""

    # the callers own name for this address, used to report the result back
    reference: str
    # as the project data names it
    address: str
    slot: GaSlot


@dataclass(frozen=True)
class ChannelRef:
    """A channel of a device.

    `channel` is a channel id of the project, or - for devices whose
    application doesn't define channels - the shared text of its communication
    objects, which is what separates the outputs of such a device.
    """

    device: str
    channel: str


@dataclass
class MappedAddress:
    """The addresses a target channel uses in place of a source address."""

    address: str
    passive: list[str] = field(default_factory=list)


@dataclass
class ChannelMapping:
    """What another channel uses instead of the source addresses."""

    target: ChannelRef
    device_name: str
    channel_name: str
    # reference -> addresses of the target channel; references that are absent
    # are device global (eg. a central switchover object) and stay as they are
    addresses: dict[str, MappedAddress] = field(default_factory=dict)
    # references that should have a counterpart but could not be resolved
    unmatched: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectIndex:
    """Lookups over project data - built once for any number of configurations."""

    project: KNXProject
    com_objects_by_device: dict[str, list[CommunicationObject]]
    devices_by_application: dict[str, list[str]]
    devices_with_channels: frozenset[str]


def build_project_index(project: KNXProject) -> ProjectIndex:
    """Index communication objects by device and devices by application.

    Project data stored by an older parser may lack some of the keys.
    """
    com_objects_by_device: dict[str, list[CommunicationObject]] = defaultdict(list)
    for com_object in project["communication_objects"].values():
        if device_address := com_object.get("device_address"):
            com_objects_by_device[device_address].append(com_object)
    devices_by_application: dict[str, list[str]] = defaultdict(list)
    devices_with_channels: set[str] = set()
    for address, device in project["devices"].items():
        if application := device.get("application"):
            devices_by_application[application].append(address)
        if device.get("channels"):
            devices_with_channels.add(address)
    return ProjectIndex(
        project=project,
        com_objects_by_device=dict(com_objects_by_device),
        devices_by_application=dict(devices_by_application),
        devices_with_channels=frozenset(devices_with_channels),
    )


def _channel_of(index: ProjectIndex, com_object: CommunicationObject) -> str | None:
    """Channel a communication object belongs to, None for device global ones.

    Applications that don't define channels separate their outputs only by the
    text of the objects ("Output A", "Channel B", …), so that is used instead.
    """
    if com_object["channel"]:
        return com_object["channel"]
    if com_object["device_address"] not in index.devices_with_channels:
        return com_object["text"] or None
    return None


def _module_of(com_object: CommunicationObject) -> dict[str, Any] | None:
    """Module instance a communication object belongs to.

    xknxproject 3.10.0 writes this as `module_def` while its
    `CommunicationObject` still declares `module`, so both names are accepted.
    """
    values = cast(dict[str, Any], com_object)
    return values.get("module_def") or values.get("module")


def _slot_allows(slot: GaSlot, com_object: CommunicationObject) -> bool:
    """Check a communication object can serve a source address in that role.

    A device acting on a command receives it, one reporting a state sends it.
    """
    flags = com_object["flags"]
    return bool(flags["write"] if slot == "write" else flags["transmit"])


def _is_dedicated(slot: GaSlot, com_object: CommunicationObject) -> bool:
    """Whether an object serves that role only, rather than both directions.

    An actuator receives commands on one object and sends its status on
    another. A push button uses a single object that does both - that is what
    tells the device acting on a group address apart from the ones operating
    it.
    """
    flags = com_object["flags"]
    if slot == "write":
        return bool(flags["write"]) and not flags["transmit"]
    return bool(flags["transmit"]) and not flags["write"]


def _rank(slot: GaSlot, com_object: CommunicationObject) -> tuple[bool, bool, int]:
    """Sort key to pick between several objects of one channel for a slot."""
    # a status object that is also readable is the better state object
    readable = slot == "state" and bool(com_object["flags"]["read"])
    return (_is_dedicated(slot, com_object), readable, -com_object["number"])


def _source_objects(
    index: ProjectIndex, addresses: list[SourceAddress]
) -> dict[str, dict[str, dict[str, CommunicationObject]]]:
    """Map device -> channel -> reference -> the object serving it."""
    project = index.project
    result: dict[str, dict[str, dict[str, CommunicationObject]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for source in addresses:
        group_address = project["group_addresses"].get(source.address)
        if group_address is None:
            continue
        for com_object_id in group_address.get("communication_object_ids", ()):
            com_object = project["communication_objects"].get(com_object_id)
            if com_object is None or not _slot_allows(source.slot, com_object):
                continue
            channel = _channel_of(index, com_object)
            if channel is None:
                continue
            by_reference = result[com_object["device_address"]][channel]
            current = by_reference.get(source.reference)
            if current is None or _rank(source.slot, com_object) > _rank(
                source.slot, current
            ):
                by_reference[source.reference] = com_object
    return result


def find_source_channels(
    index: ProjectIndex, addresses: list[SourceAddress]
) -> list[tuple[ChannelRef, dict[str, CommunicationObject]]]:
    """Find the channels a configuration is built on.

    A device qualifies through the channel covering the most of its addresses.
    Addresses reaching several channels of the same device are shared objects
    (eg. a heating/cooling switchover) and don't decide which channel it is.

    Only the best covered channels are used: a single address of a
    configuration is often linked to further devices - the room temperature of
    a thermostat also reaches an air quality sensor - and those must not be
    mistaken for the channel the configuration is actually built on.
    """
    slots = {address.reference: address.slot for address in addresses}
    candidates: list[
        tuple[tuple[int, int], ChannelRef, dict[str, CommunicationObject]]
    ] = []
    for device, by_channel in _source_objects(index, addresses).items():
        channels_per_reference = Counter(
            reference
            for by_reference in by_channel.values()
            for reference in by_reference
        )
        best: tuple[tuple[int, int], str] | None = None
        for channel, by_reference in by_channel.items():
            deciding = [
                (reference, com_object)
                for reference, com_object in by_reference.items()
                if channels_per_reference[reference] == 1
            ]
            # objects serving one direction only rank before combined ones, so
            # the actuator acting on the addresses wins over what operates it
            score = (
                len(deciding),
                sum(
                    _is_dedicated(slots[reference], com_object)
                    for reference, com_object in deciding
                ),
            )
            if score[0] and (best is None or (score, channel) > best):
                best = (score, channel)
        if best is not None:
            candidates.append(
                (best[0], ChannelRef(device, best[1]), by_channel[best[1]])
            )
    if not candidates:
        return []
    best_score = max(score for score, _, _ in candidates)
    return [
        (channel_ref, objects)
        for score, channel_ref, objects in candidates
        if score == best_score
    ]


def _channels_of(
    index: ProjectIndex, device: str
) -> dict[str, list[CommunicationObject]]:
    """Group the communication objects of a device by channel."""
    channels: dict[str, list[CommunicationObject]] = defaultdict(list)
    for com_object in index.com_objects_by_device.get(device, ()):
        if (channel := _channel_of(index, com_object)) is not None:
            channels[channel].append(com_object)
    return channels


def _same_type(first: CommunicationObject, second: CommunicationObject) -> bool:
    """Whether two objects carry the same kind of value.

    What an object of an application does can depend on its parameters - the
    same object number may switch on one channel and dim on another.
    """
    if first["dpts"] or second["dpts"]:
        return first["dpts"] == second["dpts"]
    return first["object_size"] == second["object_size"]


def _counterpart(
    source: CommunicationObject,
    candidates: list[CommunicationObject],
    same_channel_identity: bool,
) -> CommunicationObject | None:
    """Find the object of another channel taking the place of `source`.

    Only an unambiguous match is used - a channel that offers the same function
    twice would otherwise silently produce a wrong address.
    """
    candidates = [
        candidate for candidate in candidates if _same_type(source, candidate)
    ]
    if same_channel_identity:
        # an identically programmed device numbers its objects the same way
        matches = [
            candidate
            for candidate in candidates
            if candidate["number"] == source["number"]
        ]
        if len(matches) == 1:
            return matches[0]
    if module := _module_of(source):
        matches = [
            candidate
            for candidate in candidates
            if (candidate_module := _module_of(candidate)) is not None
            and candidate_module["definition"] == module["definition"]
            and candidate_module["root_number"] == module["root_number"]
        ]
        if len(matches) == 1:
            return matches[0]
    matches = [
        candidate
        for candidate in candidates
        if candidate["function_text"] == source["function_text"]
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _channel_name(project: KNXProject, target: ChannelRef) -> str:
    """Name of a channel - the project channel name or the objects text."""
    channels = project["devices"][target.device]["channels"]
    if (channel := channels.get(target.channel)) is not None:
        return channel["name"]
    return target.channel


def _map_channel(
    index: ProjectIndex,
    target: ChannelRef,
    candidates: list[CommunicationObject],
    source_objects: dict[str, CommunicationObject],
    same_channel_identity: bool,
) -> ChannelMapping:
    """Resolve the addresses one channel uses in place of the source addresses."""
    project = index.project
    mapping = ChannelMapping(
        target=target,
        device_name=project["devices"][target.device]["name"],
        channel_name=_channel_name(project, target),
    )
    for reference, source_object in source_objects.items():
        counterpart = _counterpart(source_object, candidates, same_channel_identity)
        links = [
            link
            for link in (counterpart["group_address_links"] if counterpart else ())
            if link in project["group_addresses"]
        ]
        if not links:
            mapping.unmatched.append(reference)
            continue
        mapping.addresses[reference] = MappedAddress(
            address=links[0], passive=links[1:]
        )
    return mapping


def derive_channel_mappings(
    index: ProjectIndex, addresses: list[SourceAddress]
) -> list[ChannelMapping]:
    """Report the addresses equivalent channels use instead of `addresses`.

    Covers the other channels of the device the addresses belong to and every
    channel of identically programmed devices. Channels using the very same
    addresses - eg. outputs switched in parallel - are not reported.
    """
    project = index.project
    source_addresses = {address.reference: address.address for address in addresses}
    mappings: list[ChannelMapping] = []
    for source_ref, source_objects in find_source_channels(index, addresses):
        application = project["devices"][source_ref.device]["application"]
        devices = (
            index.devices_by_application[application]
            if application
            else [source_ref.device]
        )
        for device in devices:
            for channel, candidates in _channels_of(index, device).items():
                target = ChannelRef(device, channel)
                if target == source_ref:
                    continue
                mapping = _map_channel(
                    index,
                    target,
                    candidates,
                    source_objects,
                    same_channel_identity=channel == source_ref.channel,
                )
                if any(
                    mapped.address != source_addresses[reference]
                    for reference, mapped in mapping.addresses.items()
                ):
                    mappings.append(mapping)
    return mappings
