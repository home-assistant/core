"""Device identity helpers for Hikvision."""

import uuid

from homeassistant.config_entries import ConfigEntry

from .const import CONF_RANDOM_ID


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
