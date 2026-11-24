"""Device identity helpers for Hikvision."""

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
import json
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_RANDOM_ID, DOMAIN


def is_random_id_made_up(camera_id: object) -> bool:
    """Return whether pyHik made up the ID it gives, a random one.

    pyHik gives a device's own ID as a string, also one that is a UUID, and only
    one it makes up as a UUID object: a random one (version 4) before 0.5.1, a
    stable one derived from the serial or MAC address (version 5) since.
    """
    return isinstance(camera_id, uuid.UUID) and camera_id.version == 4


def looks_made_up(unique_id: object) -> bool:
    """Return whether a unique ID has the form of a random one pyHik makes up.

    Only a guess, for an entry that did not record where its ID came from: a
    device's own ID can be a random UUID too.
    """
    if unique_id is None:
        return False
    # Entries created before the user flow stored a string kept pyHik's UUID object.
    unique_id = str(unique_id)
    try:
        parsed = uuid.UUID(unique_id)
    except ValueError:
        return False
    return str(parsed) == unique_id and parsed.version == 4


def is_made_up_id(entry: ConfigEntry) -> bool:
    """Return whether an entry's unique ID is a random one pyHik made up.

    pyHik before 0.5.1 makes up a random UUID for a device whose own ID is too
    short, a new one at every connection: such an entry cannot be checked against
    the device it reaches. Any other ID is, including the stable one later versions
    derive: two devices with different derived IDs are different devices.

    Where the ID came from is recorded when the entry is created; an entry created
    before that falls back to the form of its ID.
    """
    if (random_id := entry.data.get(CONF_RANDOM_ID)) is not None:
        return bool(random_id)
    return looks_made_up(entry.unique_id)


def made_up_prefix(identifier: str, device_id: str) -> tuple[str, str] | None:
    """Split an identifier made with another made-up ID into that ID and the rest.

    The unique IDs and device identifiers start with the device's ID, then "_" and
    the rest, if any. A UUID has no "_" in it.
    """
    old_id, separator, rest = identifier.partition("_")
    if old_id == device_id or not looks_made_up(old_id):
        return None
    return old_id, separator + rest


def oldest[_T](
    candidates: Iterable[_T], created_at: Callable[[_T], datetime]
) -> _T | None:
    """Return the candidate registered first, or None if that cannot be told.

    Registry entries older than the date of creation were all given the same
    one when it was added, so several can share the earliest date: none of them
    is then known to be the first, and the order of the registry tells nothing.
    """
    candidates = list(candidates)
    first = min(created_at(candidate) for candidate in candidates)
    earliest = [c for c in candidates if created_at(c) == first]
    return earliest[0] if len(earliest) == 1 else None


@callback
def async_earlier_devices(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str
) -> dict[str, list[tuple[dr.DeviceEntry, tuple[str, str]]]]:
    """Return the entry's devices registered under earlier made-up IDs.

    Each with the identifier it has under such an ID, grouped by the rest of the
    identifier: the device, or a channel of it, that the entry's ID now stands for.
    """
    groups: dict[str, list[tuple[dr.DeviceEntry, tuple[str, str]]]] = {}
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and (split := made_up_prefix(identifier, device_id)):
                groups.setdefault(split[1], []).append((device, (domain, identifier)))
    return groups


@callback
def async_earlier_entities(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str
) -> dict[tuple[str, str], list[er.RegistryEntry]]:
    """Return the entry's entities registered under earlier made-up IDs.

    Grouped by their platform and the rest of their unique ID: the entity that the
    entry's ID now stands for.
    """
    groups: dict[tuple[str, str], list[er.RegistryEntry]] = {}
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if split := made_up_prefix(entity.unique_id, device_id):
            groups.setdefault((entity.domain, split[1]), []).append(entity)
    return groups


@callback
def async_move_device(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    old_identifier: tuple[str, str],
    new_identifier: tuple[str, str],
) -> None:
    """Give a device the identifier of the entry's ID in place of an earlier one."""
    dev_reg = dr.async_get(hass)
    # As it is now: an earlier move may have changed its identifiers.
    if (current := dev_reg.async_get(device.id)) is None:
        return
    dev_reg.async_update_device(
        device.id,
        new_identifiers=(set(current.identifiers) - {old_identifier})
        | {new_identifier},
    )


def ambiguous_identities_issue_id(entry_id: str) -> str:
    """Return the ID of the repair issue that asks which earlier identity to keep."""
    return f"ambiguous_identities_{entry_id}"


def encode_ambiguous_identities(
    entry_id: str, devices: list[str], entities: list[list[str]]
) -> dict[str, str | int | float | None]:
    """Return the data of the repair issue for these devices and entities.

    A device is the rest of its identifier, an entity its platform and the rest of
    its unique ID. Issue data holds plain values only, so the lists are JSON.
    """
    return {
        "entry_id": entry_id,
        "devices": json.dumps(devices),
        "entities": json.dumps(entities),
    }


def decode_ambiguous_identities(
    data: Mapping[str, object],
) -> tuple[list[str], list[list[str]]]:
    """Return the devices and entities that the data of the repair issue holds."""
    return json.loads(str(data["devices"])), json.loads(str(data["entities"]))


@callback
def async_link_to_kept_devices(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str
) -> None:
    """Link the entry's entities and channel devices to the devices of its ID.

    Run once the device of the entry's ID is registered, which a setup does for
    an NVR that none was kept for.

    An entity, or the channel of an NVR, kept from one earlier setup can still be
    linked to a device of another, one that was not kept. A reload only moves what
    the camera still has, so the links are set here: an entity of the entry's ID
    goes to the kept device of the same camera or channel, and each channel of the
    entry's ID is linked through the kept NVR.
    """
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    # The device of the entry's ID for each camera or channel, by the rest of its
    # identifier; and the camera or channel each of the entry's devices is for.
    kept: dict[str, str] = {}
    rest_of: dict[str, str] = {}
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            if identifier == device_id or identifier.startswith(f"{device_id}_"):
                rest = identifier.removeprefix(device_id)
                kept[rest] = device.id
                rest_of[device.id] = rest
            elif split := made_up_prefix(identifier, device_id):
                rest_of.setdefault(device.id, split[1])
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if (
            entity.device_id is None
            or made_up_prefix(entity.unique_id, device_id) is not None
            or (entity_rest := rest_of.get(entity.device_id)) is None
            or (target := kept.get(entity_rest)) is None
        ):
            continue
        if target != entity.device_id:
            ent_reg.async_update_entity(entity.entity_id, device_id=target)
    if (nvr := kept.get("")) is None:
        return
    for rest, channel_id in kept.items():
        if (
            rest
            and isinstance(channel := dev_reg.async_get(channel_id), dr.DeviceEntry)
            # Unlinked too: removing an earlier NVR unlinks its channels.
            and channel.via_device_id != nvr
        ):
            dev_reg.async_update_device(channel_id, via_device_id=nvr)
