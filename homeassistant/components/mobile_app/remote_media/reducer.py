"""Keep a followed player's card meaningful across the states integrations actually emit.

Not an optimisation: when an APNs push cold-launches the RemoteMedia extension, that process has no
prior snapshot, so the pushed attributes are the whole truth. A transient `idle` with blank metadata
sent as if it were the complete picture leaves the user an empty card.

A mirror of Swift `RemoteMediaSnapshotReducer`. The rules are a general resilience policy and
deliberately not keyed on any integration.
"""

from dataclasses import replace

from .model import RemoteMediaSnapshot


def reduce_snapshot(
    previous: RemoteMediaSnapshot | None, incoming: RemoteMediaSnapshot
) -> RemoteMediaSnapshot | None:
    """Return what the card should show, or None if nothing meaningful has been seen yet."""
    if incoming.has_meaningful_media:
        # Taken wholesale, so a new track keeps none of the previous one's identity: the app pairs
        # artwork with the track it belongs to, and mixing them shows the last song's cover over
        # this one's title.
        return incoming

    # Nothing meaningful in this report. With nothing to fall back on there is nothing to show;
    # the player stays followed, so the next meaningful report starts the card.
    if previous is None or not previous.has_meaningful_media:
        return None

    # Keep the media and describe the transition. `unavailable` and `unknown` mean the integration
    # stopped reporting, which is not the same as having stopped, so the last known playback state
    # is kept rather than a new one invented. Position is held too: extrapolating from a blank
    # report would make the card scrub while nothing is playing.
    retained_state = (
        previous.state if incoming.playback == "indeterminate" else incoming.state
    )
    return replace(previous, state=retained_state)
