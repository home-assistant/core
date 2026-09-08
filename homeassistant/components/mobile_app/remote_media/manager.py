"""Watch followed players and push only what matters.

Core is the primary traffic shaper for Remote Now Playing. The relay has a safety ceiling, but a
playing media player emits a state event every few seconds and almost none of them are worth
waking a phone for: the card advances its own position from `position` and
`positionUpdatedAtUnix`, so ordinary progress needs no push at all.

Three mechanisms, in order:

* the reducer keeps a meaningful picture across the noise integrations emit,
* a short coalescing window collapses a burst of contradictory events into its outcome,
* a change test decides whether the outcome differs from what the card already shows.
"""

from dataclasses import replace
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity_registry import EventEntityRegistryUpdatedData
from homeassistant.helpers.event import (
    async_call_later,
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)

from ..const import (
    ATTR_APP_DATA,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_WEBHOOK_ID,
    DATA_CONFIG_ENTRIES,
    DATA_REMOTE_MEDIA_MANAGER,
    DOMAIN,
)
from .const import (
    ATTR_GENERATION,
    ATTR_SNAPSHOT,
    ATTR_WIRE_GENERATION_SEQUENCE,
    COALESCE_SECONDS,
    CONFIGURATION_BACKOFF_SECONDS,
    EVENT_END,
    EVENT_UPDATE,
    MAXIMUM_RETRY_BACKOFF_SECONDS,
    RATE_LIMIT_BACKOFF_SECONDS,
    RETRY_BACKOFF_SECONDS,
    SEEK_TOLERANCE_SECONDS,
    VOLUME_CHANGE_THRESHOLD,
)
from .mapper import snapshot_from_state
from .model import RemoteMediaSession, RemoteMediaSnapshot
from .push import PushOutcome, async_send
from .reducer import reduce_snapshot
from .store import async_load_sessions, async_remove_session, async_save_session

_LOGGER = logging.getLogger(__name__)


def is_meaningful_change(
    published: RemoteMediaSnapshot | None, candidate: RemoteMediaSnapshot
) -> bool:
    """Whether `candidate` differs from what the card already shows in a way worth a push.

    The expensive mistake here is pushing ordinary progress. A playing track reports a new
    `media_position` and `media_position_updated_at` every few seconds, and the card is already
    extrapolating between them, so those updates carry no information. A seek does — and it is
    told apart by comparing the reported position against where playback would have reached.
    """
    if published is None:
        return True
    # The card issues its commands against the selection it was given, so a player that has been
    # renamed has to be sent even when nothing about the media changed.
    if published.entity_id != candidate.entity_id:
        return True
    if published.server_id != candidate.server_id:
        return True
    if published.track_id != candidate.track_id:
        return True
    # The same track can change its cover — a station updating its art, or an integration that
    # reports the picture a moment after the metadata.
    if published.artwork_url != candidate.artwork_url:
        return True
    if published.playback != candidate.playback:
        return True
    if published.features != candidate.features:
        return True
    if published.duration != candidate.duration:
        return True
    if published.device_name != candidate.device_name:
        return True
    if published.device_class != candidate.device_class:
        return True
    if published.is_muted != candidate.is_muted:
        return True
    if _volume_moved(published.volume, candidate.volume):
        return True
    return _position_jumped(published, candidate)


def _volume_moved(previous: float | None, current: float | None) -> bool:
    """Whether the volume changed enough to matter."""
    if previous is None or current is None:
        return previous is not current
    return abs(previous - current) >= VOLUME_CHANGE_THRESHOLD


def _position_jumped(
    published: RemoteMediaSnapshot, candidate: RemoteMediaSnapshot
) -> bool:
    """Whether the position moved somewhere playback would not have taken it.

    While playing, the position expected now is the last one plus the time since it was measured.
    A report inside `SEEK_TOLERANCE_SECONDS` of that is progress and is ignored; further away is a
    seek and is worth a push. While not playing, any real movement is a seek.
    """
    if candidate.position is None:
        # Losing a position is only interesting if we had one to lose.
        return published.position is not None
    if published.position is None:
        return True

    elapsed = 0.0
    if published.playback == "playing":
        if (
            published.position_updated_at_unix is not None
            and candidate.position_updated_at_unix is not None
        ):
            elapsed = max(
                0.0,
                candidate.position_updated_at_unix - published.position_updated_at_unix,
            )
        else:
            # No timestamps to reason with: treat progress as unknowable rather than as a seek.
            return False

    expected = published.position + elapsed
    return abs(candidate.position - expected) > SEEK_TOLERANCE_SECONDS


def _with_entity_id(
    snapshot: RemoteMediaSnapshot | None, entity_id: str
) -> RemoteMediaSnapshot | None:
    """Return `snapshot` describing `entity_id`, or None if there was no snapshot."""
    if snapshot is None or snapshot.entity_id == entity_id:
        return snapshot
    return replace(snapshot, entity_id=entity_id)


@callback
def can_cloud_push(entry: ConfigEntry) -> bool:
    """Whether this registration can be reached through the push relay at all.

    A registration without a push URL and token is local-push only. Following a player for it would
    mean shaping traffic forever to produce requests that can never be sent.
    """
    app_data = entry.data.get(ATTR_APP_DATA, {})
    return bool(app_data.get(ATTR_PUSH_URL)) and bool(app_data.get(ATTR_PUSH_TOKEN))


class RemoteMediaSessionPublisher:
    """One Follow relationship: its sticky state, its clock, and its single sender.

    Sends are serialised: a burst produces one request in flight and, when it finishes, one more
    carrying the newest desired state, never a queue of stale ones.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        webhook_id: str,
        session: RemoteMediaSession,
    ) -> None:
        """Set up a publisher for a stored session."""
        self.hass = hass
        self.webhook_id = webhook_id
        self.session = session
        # What the card is believed to show, and what we would like it to show.
        self._effective: RemoteMediaSnapshot | None = session.last_snapshot
        self._published: RemoteMediaSnapshot | None = session.last_snapshot
        self._pending: RemoteMediaSnapshot | None = None
        # The newest snapshot waiting to go out. Replaced rather than queued, so a burst of
        # changes can never become a backlog of stale requests.
        self._desired: RemoteMediaSnapshot | None = None
        self._in_flight: RemoteMediaSnapshot | None = None
        self._cancel_coalesce: CALLBACK_TYPE | None = None
        # Armed only while an update is actually owed. See `RETRY_BACKOFF_SECONDS`.
        self._cancel_retry: CALLBACK_TYPE | None = None
        self._retry_delay = RETRY_BACKOFF_SECONDS
        self._sending = False
        self._quiet_until = 0.0
        self._reported_misconfiguration: str | None = None
        self._removed = False

    @property
    def entity_id(self) -> str:
        """The followed player."""
        return self.session.entity_id

    @callback
    def async_shutdown(self) -> None:
        """Retire the publisher and drop timers so nothing fires after it is gone."""
        self._removed = True
        if self._cancel_coalesce is not None:
            self._cancel_coalesce()
            self._cancel_coalesce = None
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    @callback
    def async_rename_entity(self, entity_id: str) -> None:
        """Point this relationship at the same player under a new entity id.

        Nothing the phone identifies the session by changes, and neither does the sticky picture of
        what is playing.
        """
        self.session.entity_id = entity_id
        self._effective = _with_entity_id(self._effective, entity_id)
        self._pending = _with_entity_id(self._pending, entity_id)
        self._desired = _with_entity_id(self._desired, entity_id)
        # `_published` keeps the old name: it records what the phone was last told, and that
        # difference is what makes the rename a change worth pushing.

    @callback
    def async_apply(self, snapshot: RemoteMediaSnapshot | None) -> None:
        """Fold one report into the effective state and consider publishing it.

        Every report is reduced, because that is how the sticky picture accumulates; only the
        outcome of a settling window is considered for a push.
        """
        if self._removed or snapshot is None:
            return

        reduced = reduce_snapshot(self._effective, snapshot)
        if reduced is None:
            # Nothing meaningful has ever been seen for this player. Stay registered and wait.
            return
        self._effective = reduced
        self._pending = reduced

        if self._cancel_coalesce is None:
            self._cancel_coalesce = async_call_later(
                self.hass, COALESCE_SECONDS, self._async_coalesced
            )

    @callback
    def _async_coalesced(self, _now: Any) -> None:
        """Publish the settled outcome of a burst, if it says anything new."""
        self._cancel_coalesce = None
        pending = self._pending
        self._pending = None
        if pending is None or self._removed:
            return
        if not is_meaningful_change(self._published, pending):
            if self._in_flight is not None:
                # The phone may still receive the older in-flight snapshot. Keep the settled
                # state as a supersession marker until that result is known.
                self._desired = pending
            else:
                self._desired = None
                if self._cancel_retry is not None:
                    self._cancel_retry()
                    self._cancel_retry = None
            return
        self.async_publish(pending)

    @callback
    def async_publish(self, snapshot: RemoteMediaSnapshot) -> None:
        """Queue a snapshot for delivery, coalescing with anything already in flight."""
        if self._removed:
            return
        self._desired = snapshot
        if self._sending:
            # The in-flight send picks up whatever is newest when it finishes.
            return
        self.hass.async_create_task(
            self._async_drain(), name=f"remote_media publish {self.session.session_id}"
        )

    async def _async_drain(self) -> None:
        """Send the newest desired snapshot until nothing newer is waiting.

        What is owed stays in `_desired` until it has been delivered. An update the relay refused,
        or one held back by a quiet period, is still the current state of the player, so it is
        offered again rather than discarded in the hope the player says something else soon.
        """
        if self._sending:
            return
        self._sending = True
        try:
            while not self._removed:
                snapshot = self._desired
                if snapshot is None:
                    return
                if (quiet_for := self._quiet_until - time.time()) > 0:
                    # Still owed, so it is left in place and offered again when the quiet period
                    # ends rather than waiting on a state change that may never come.
                    self._async_schedule_retry(quiet_for)
                    return
                self._desired = None
                self._in_flight = snapshot
                try:
                    outcome = await self._async_send(EVENT_UPDATE, snapshot)
                except Exception:
                    # The send itself came apart. The snapshot is no less current for it, so it
                    # is treated exactly like a refusal rather than vanishing with the traceback.
                    _LOGGER.exception(
                        "Could not send a Remote Now Playing update for %s",
                        self.entity_id,
                    )
                    outcome = None
                finally:
                    self._in_flight = None
                if outcome is PushOutcome.DELIVERED:
                    if self._desired is not None and not is_meaningful_change(
                        self._published, self._desired
                    ):
                        self._desired = None
                    continue
                if self._removed:
                    return
                if self._desired is None:
                    # Nothing newer arrived while that was failing, so this is still what the
                    # phone is missing. Anything newer is already in `_desired` and supersedes it.
                    self._desired = snapshot
                if not is_meaningful_change(self._published, self._desired):
                    self._desired = None
                    return
                # Never before a quiet period is over, or the timer is spent on a send that is
                # only going to be held back again.
                self._async_schedule_retry(
                    max(self._retry_delay, self._quiet_until - time.time())
                )
                self._retry_delay = min(
                    self._retry_delay * 2, MAXIMUM_RETRY_BACKOFF_SECONDS
                )
                return
        finally:
            self._sending = False

    @callback
    def _async_schedule_retry(self, delay: float) -> None:
        """Offer the outstanding update again after `delay`.

        One timer at a time, and only while something is owed: re-arming on every failure would
        stack timers, and arming with nothing outstanding would be a poll.
        """
        if self._removed or self._cancel_retry is not None:
            return
        self._cancel_retry = async_call_later(
            self.hass, max(delay, 0.0), self._async_retry
        )

    @callback
    def _async_retry(self, _now: Any) -> None:
        """Put the outstanding update back through the ordinary send path."""
        self._cancel_retry = None
        if self._removed or (snapshot := self._desired) is None:
            return
        self.async_publish(snapshot)

    async def async_send_end(self, entry: ConfigEntry | None = None) -> None:
        """Tell the card its session is over. Best effort: cleanup never depends on this.

        `entry` is passed in when the registration is being removed, because unloading has already
        taken it out of `DATA_CONFIG_ENTRIES` by then.
        """
        if (snapshot := self._effective) is None:
            snapshot = self._published
        await self._async_send(EVENT_END, snapshot, mark_published=False, entry=entry)

    async def _async_send(
        self,
        event: str,
        snapshot: RemoteMediaSnapshot | None,
        *,
        mark_published: bool = True,
        entry: ConfigEntry | None = None,
    ) -> PushOutcome | None:
        """Build attributes, send them, and act on the answer.

        Returns what the relay said, so the caller can tell an update that landed from one that is
        still owed. `None` means there was no registration to send through at all.
        """
        if mark_published and self._removed:
            return None
        if entry is None:
            entry = self._entry()
        if entry is None:
            return None

        timestamp = self._next_timestamp()
        attributes = self.build_attributes(event, snapshot)
        result = await async_send(
            self.hass,
            entry,
            self.session.session_id,
            self.session.push_token,
            event,
            timestamp,
            attributes,
        )

        # A replacement or teardown may have retired this publisher while the transport was
        # waiting. Its result belongs to the old lifetime and must not change the new session's
        # persisted token, snapshot, or retry state.
        if self._removed:
            return result.outcome

        # The clock advances even on failure, so a retry can never reuse an ordering value APNs
        # has already seen for this session.
        self.session.last_timestamp = timestamp

        if result.outcome is PushOutcome.DELIVERED:
            self._reported_misconfiguration = None
            self._retry_delay = RETRY_BACKOFF_SECONDS
            if mark_published and snapshot is not None:
                self._published = snapshot
                self.session.last_snapshot = snapshot
            if mark_published:
                async_save_session(self.hass, self.webhook_id, self.session)
            return result.outcome

        if result.outcome is PushOutcome.REMOVE:
            _LOGGER.debug(
                "Push relay reports the Remote Now Playing token for session %s is no longer"
                " valid; removing the registration",
                self.session.session_id,
            )
            async_get_manager(self.hass).async_remove_invalid_token(self)
            return result.outcome

        if result.outcome is PushOutcome.BACK_OFF:
            self._quiet_until = time.time() + RATE_LIMIT_BACKOFF_SECONDS
            _LOGGER.debug(
                "Remote Now Playing updates for session %s are rate limited; pausing",
                self.session.session_id,
            )
        elif result.outcome is PushOutcome.MISCONFIGURED:
            self._quiet_until = time.time() + CONFIGURATION_BACKOFF_SECONDS
            # Complained about once per condition, not once per state change of a playing player.
            if self._reported_misconfiguration != result.error_type:
                self._reported_misconfiguration = result.error_type
                _LOGGER.warning(
                    "The push relay will not deliver Remote Now Playing updates for %s: %s."
                    " Keeping the registration and pausing updates",
                    self.entity_id,
                    result.error_type,
                )

        if mark_published:
            async_save_session(self.hass, self.webhook_id, self.session)
        return result.outcome

    def build_attributes(
        self, event: str, snapshot: RemoteMediaSnapshot | None
    ) -> dict[str, Any]:
        """Return the attributes object the iOS app decodes.

        `id` is the identifier the app registered, echoed verbatim: iOS routes the push by it, and
        a payload without it is accepted by APNs and then discarded by the device. The relationship
        travels with it so a cold-launched extension can register its token against the right one.
        """
        attributes: dict[str, Any] = {
            ATTR_ID: self.session.session_id,
            ATTR_GENERATION: self.session.generation,
        }
        if self.session.generation_sequence is not None:
            attributes[ATTR_WIRE_GENERATION_SEQUENCE] = self.session.generation_sequence
        if event == EVENT_END:
            # Ending needs only the identity, and the app may already have torn the session down.
            return attributes
        if snapshot is not None:
            attributes[ATTR_SNAPSHOT] = snapshot.as_wire()
        return attributes

    def _next_timestamp(self) -> int:
        """Return the next strictly increasing ordering value for this session.

        APNs sequences a session's pushes by this, and several meaningful changes can land inside
        one second, so wall-clock seconds alone would let the device apply them out of order. It
        is persisted, so a restart cannot go backwards either. Not to be confused with
        `positionUpdatedAtUnix`, which is when playback position was measured.
        """
        now = int(time.time())
        previous = self.session.last_timestamp
        return now if previous is None else max(now, previous + 1)

    def _entry(self) -> ConfigEntry | None:
        """The config entry that owns this session, if it is still loaded."""
        # pylint: disable-next=home-assistant-use-runtime-data
        return self.hass.data[DOMAIN][DATA_CONFIG_ENTRIES].get(self.webhook_id)


class RemoteMediaEntityWatcher:
    """One Home Assistant state listener, shared by every session following the same player.

    Two devices can follow the same speaker, so the watcher maps each event once and hands the
    result to every publisher.

    It also watches the entity registry, which is where the difference between "gone for a moment"
    and "gone" lives: a state going to `None` is transient, a registry removal is not, and a
    registry rename is the same entity that a relationship should follow.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Set up a watcher with no subscribers yet."""
        self.hass = hass
        self.entity_id = entity_id
        self.publishers: dict[tuple[str, str], RemoteMediaSessionPublisher] = {}
        self._unsubscribe: CALLBACK_TYPE | None = None
        self._unsubscribe_registry: CALLBACK_TYPE | None = None

    @callback
    def async_add(
        self, key: tuple[str, str], publisher: RemoteMediaSessionPublisher
    ) -> None:
        """Start following, and start listening if this is the first subscriber."""
        self.publishers[key] = publisher
        if self._unsubscribe is None:
            self._unsubscribe = async_track_state_change_event(
                self.hass, [self.entity_id], self._async_state_changed
            )
        if self._unsubscribe_registry is None:
            self._unsubscribe_registry = async_track_entity_registry_updated_event(
                self.hass, [self.entity_id], self._async_registry_updated
            )

    @callback
    def async_remove(self, key: tuple[str, str]) -> bool:
        """Stop following, returning whether the watcher is now unused."""
        self.publishers.pop(key, None)
        if self.publishers:
            return False
        self.async_shutdown()
        return True

    @callback
    def async_shutdown(self) -> None:
        """Detach the listeners."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._unsubscribe_registry is not None:
            self._unsubscribe_registry()
            self._unsubscribe_registry = None

    @callback
    def async_reconcile(self) -> None:
        """Feed the player's current state to every subscriber.

        Used when a session is registered and after a restart, so the card is brought up to date
        without waiting for the player to change.
        """
        if (state := self.hass.states.get(self.entity_id)) is None:
            return
        for publisher in list(self.publishers.values()):
            publisher.async_apply(
                snapshot_from_state(state, publisher.session.server_id)
            )

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle one state change for the followed player."""
        new_state = event.data["new_state"]

        if new_state is None:
            # Transient by definition. An integration reload, a platform reload and startup
            # ordering all remove and restore entities, and there is no length of time that tells
            # those apart from a deletion — the registry does that, so this waits. The card keeps
            # showing what it had; the user can always stop following.
            _LOGGER.debug(
                "%s has no state for the moment; keeping the Remote Now Playing sessions"
                " following it",
                self.entity_id,
            )
            return

        for publisher in list(self.publishers.values()):
            publisher.async_apply(
                snapshot_from_state(new_state, publisher.session.server_id)
            )

    @callback
    def _async_registry_updated(
        self, event: Event[EventEntityRegistryUpdatedData]
    ) -> None:
        """Act on the entity registry, which is where permanence is decided."""
        data = event.data
        manager = async_get_manager(self.hass)

        if data["action"] == "remove":
            _LOGGER.debug(
                "%s has been removed from the entity registry; ending the Remote Now Playing"
                " sessions following it",
                self.entity_id,
            )
            for key in list(self.publishers):
                manager.async_end_session(*key)
            return

        if data["action"] != "update":
            return
        if (old_entity_id := data.get("old_entity_id")) is None:
            return
        # A rename. The relationship is with the player, not with the string, so it moves — and
        # the session identifier, the relationship and the push token all stay as they are,
        # because none of them has anything to do with what the entity is called.
        _LOGGER.debug(
            "%s has been renamed to %s; moving the Remote Now Playing sessions following it",
            old_entity_id,
            data["entity_id"],
        )
        manager.async_rename_entity(old_entity_id, data["entity_id"])


class RemoteMediaManager:
    """Owns every active Follow relationship and the listeners behind them."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up an empty manager."""
        self.hass = hass
        self.publishers: dict[tuple[str, str], RemoteMediaSessionPublisher] = {}
        self.watchers: dict[str, RemoteMediaEntityWatcher] = {}
        # Relationships stored for a registration that cannot be pushed to. Kept so the phone
        # does not have to notice and re-register, watched only once it can be reached.
        self.dormant: dict[tuple[str, str], RemoteMediaSession] = {}

    @callback
    def async_restore(
        self, entry: ConfigEntry, sessions: list[RemoteMediaSession]
    ) -> None:
        """Bring one registration's stored sessions back after a restart or reload."""
        webhook_id = entry.data[ATTR_WEBHOOK_ID]
        for session in sessions:
            self.async_add(webhook_id, session, entry, reconcile=True)

    @callback
    def async_add(
        self,
        webhook_id: str,
        session: RemoteMediaSession,
        entry: ConfigEntry,
        *,
        reconcile: bool,
    ) -> RemoteMediaSessionPublisher | None:
        """Start following for one session, replacing any publisher it supersedes.

        Returns `None` for a registration with no way of being pushed to: the relationship is
        remembered, but nothing is watched, reduced or coalesced for it. See
        `async_registration_updated` for how it starts once the registration gains push.
        """
        key = (webhook_id, session.session_id)
        if (existing := self.publishers.get(key)) is not None:
            self._async_detach(key, existing)
        self.dormant.pop(key, None)

        if not can_cloud_push(entry):
            _LOGGER.debug(
                "Keeping the Remote Now Playing registration for %s without watching it: this"
                " Home Assistant registration has no cloud push configuration",
                session.entity_id,
            )
            self.dormant[key] = session
            return None

        publisher = RemoteMediaSessionPublisher(self.hass, webhook_id, session)
        self.publishers[key] = publisher

        watcher = self.watchers.get(session.entity_id)
        if watcher is None:
            watcher = RemoteMediaEntityWatcher(self.hass, session.entity_id)
            self.watchers[session.entity_id] = watcher
        watcher.async_add(key, publisher)

        if reconcile:
            watcher.async_reconcile()
        return publisher

    @callback
    def async_registration_updated(self, entry: ConfigEntry) -> None:
        """Start watching relationships this registration can now be pushed to.

        Called when `update_registration` changes a registration's app data, which is where a
        Companion install that had no push gains it. Nothing here starts a relationship the user
        did not ask for: only sessions already stored for this registration are picked up.
        """
        webhook_id = entry.data[ATTR_WEBHOOK_ID]
        if not can_cloud_push(entry):
            for key in [key for key in self.publishers if key[0] == webhook_id]:
                publisher = self.publishers[key]
                self._async_detach(key, publisher)
                self.dormant[key] = publisher.session
            return

        waiting = [key for key in self.dormant if key[0] == webhook_id]
        if not waiting:
            return
        for key in waiting:
            session = self.dormant[key]
            _LOGGER.debug(
                "This Home Assistant registration can be pushed to now; following %s for Remote"
                " Now Playing",
                session.entity_id,
            )
            self.async_add(webhook_id, session, entry, reconcile=True)

    @callback
    def async_rename_entity(self, old_entity_id: str, new_entity_id: str) -> None:
        """Follow the same player under its new entity id.

        The relationship is with the player, so only the stored entity id, the listener it hangs
        off and the snapshot the card next sees change.
        """
        if old_entity_id == new_entity_id:
            return

        if (watcher := self.watchers.get(old_entity_id)) is not None:
            moved = self.watchers.get(new_entity_id)
            if moved is None:
                moved = RemoteMediaEntityWatcher(self.hass, new_entity_id)
                self.watchers[new_entity_id] = moved
            for key, publisher in list(watcher.publishers.items()):
                publisher.async_rename_entity(new_entity_id)
                async_save_session(self.hass, key[0], publisher.session)
                if watcher.async_remove(key):
                    self.watchers.pop(old_entity_id, None)
                moved.async_add(key, publisher)
            # The card carries the entity it should send commands to, so the phone has to be told
            # the new name — the snapshot differing by selection alone is a meaningful change.
            moved.async_reconcile()

        for key, session in list(self.dormant.items()):
            if session.entity_id == old_entity_id:
                session.entity_id = new_entity_id
                async_save_session(self.hass, key[0], session)

    @callback
    def async_get(
        self, webhook_id: str, session_id: str
    ) -> RemoteMediaSessionPublisher | None:
        """The publisher for one session, if it is being watched."""
        return self.publishers.get((webhook_id, session_id))

    @callback
    def async_is_known(self, webhook_id: str, session_id: str) -> bool:
        """Whether this relationship is set up at all, watched or dormant.

        A stored session that neither knows about is one this run has not picked up yet, so an
        otherwise identical re-registration has to be allowed to attach it.
        """
        key = (webhook_id, session_id)
        return key in self.publishers or key in self.dormant

    @callback
    def async_end_session(
        self, webhook_id: str, session_id: str, entry: ConfigEntry | None = None
    ) -> None:
        """Remove one session and tell the card, best effort.

        `entry` is only needed when the owning registration is being removed, because unloading
        has already taken it out of `DATA_CONFIG_ENTRIES` by then.
        """
        key = (webhook_id, session_id)
        if (publisher := self.publishers.get(key)) is None:
            if self.dormant.pop(key, None) is not None:
                # Nothing was ever watched and nothing can be pushed to, so there is no card to
                # tell — just forget the relationship.
                async_remove_session(self.hass, webhook_id, session_id)
            return
        self.hass.async_create_task(
            self._async_end(publisher, entry), name=f"remote_media end {session_id}"
        )
        async_remove_session(self.hass, webhook_id, session_id)
        self._async_detach(key, publisher)

    @callback
    def async_remove_invalid_token(
        self, publisher: RemoteMediaSessionPublisher
    ) -> None:
        """Remove and detach a session whose relay token is no longer valid."""
        key = (publisher.webhook_id, publisher.session.session_id)
        async_remove_session(self.hass, *key)
        self.dormant.pop(key, None)
        if self.publishers.get(key) is publisher:
            self._async_detach(key, publisher)
        else:
            publisher.async_shutdown()

    @callback
    def async_end_registration(self, entry: ConfigEntry) -> None:
        """Tell every card this registration owns that it is over, best effort.

        Works from stored state rather than from live publishers, because unloading has already
        detached them all by the time a removal runs.
        """
        webhook_id = entry.data[ATTR_WEBHOOK_ID]
        for session in async_load_sessions(self.hass, webhook_id):
            key = (webhook_id, session.session_id)
            if key in self.dormant:
                # Never reachable, so there is no card to tell.
                continue
            publisher = self.publishers.get(key) or RemoteMediaSessionPublisher(
                self.hass, webhook_id, session
            )
            self.hass.async_create_task(
                self._async_end(publisher, entry),
                name=f"remote_media end {session.session_id}",
            )

    async def _async_end(
        self, publisher: RemoteMediaSessionPublisher, entry: ConfigEntry | None = None
    ) -> None:
        """Send `end` without letting a failure hold up cleanup."""
        try:
            await publisher.async_send_end(entry)
        except Exception:
            _LOGGER.debug(
                "Could not tell the phone its Remote Now Playing session ended",
                exc_info=True,
            )

    @callback
    def async_unload_registration(self, webhook_id: str) -> None:
        """Detach one registration's listeners, keeping its stored sessions.

        Used when a config entry unloads. The Follow relationship is not over, so only the runtime
        goes — listeners, timers and in-flight bookkeeping — and it is rebuilt from stored state
        when the entry is set up again.
        """
        for key in [key for key in self.publishers if key[0] == webhook_id]:
            publisher = self.publishers[key]
            self._async_detach(key, publisher)
        # A dormant relationship has no runtime to drop, but it must not be left pointing at an
        # entry that is gone: it is picked up again from the store when the entry returns.
        for key in [key for key in self.dormant if key[0] == webhook_id]:
            del self.dormant[key]

    @callback
    def _async_detach(
        self, key: tuple[str, str], publisher: RemoteMediaSessionPublisher
    ) -> None:
        """Take one publisher off its watcher, dropping the listener if it was the last."""
        self.publishers.pop(key, None)
        publisher.async_shutdown()
        if (watcher := self.watchers.get(publisher.entity_id)) is None:
            return
        if watcher.async_remove(key):
            del self.watchers[publisher.entity_id]


@callback
def async_get_manager(hass: HomeAssistant) -> RemoteMediaManager:
    """Return the manager, creating it on first use."""
    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data[DOMAIN]
    if (manager := domain_data.get(DATA_REMOTE_MEDIA_MANAGER)) is None:
        manager = RemoteMediaManager(hass)
        domain_data[DATA_REMOTE_MEDIA_MANAGER] = manager
    return manager
