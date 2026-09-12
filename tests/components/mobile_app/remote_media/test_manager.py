"""Traffic shaping, ordering and lifecycle for a followed player.

Core is the primary traffic shaper. A playing media player emits a state event every few seconds
and almost none of them are worth waking a phone for, because the card advances its own position
between updates.
"""

import asyncio
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.mobile_app.const import DATA_REMOTE_MEDIA_SESSIONS, DOMAIN
from homeassistant.components.mobile_app.remote_media.const import (
    COALESCE_SECONDS,
    MAXIMUM_RETRY_BACKOFF_SECONDS,
    RETRY_BACKOFF_SECONDS,
)
from homeassistant.components.mobile_app.remote_media.manager import (
    async_get_manager,
    is_meaningful_change,
)
from homeassistant.components.mobile_app.remote_media.model import (
    RemoteMediaSession,
    RemoteMediaSnapshot,
)
from homeassistant.components.mobile_app.remote_media.store import async_save_session
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import WEBHOOK_ID, session
from .const import (
    ENTITY_ID,
    GENERATION,
    LATER_PUSH_TOKEN,
    PLAYING_ATTRIBUTES,
    PUSH_TOKEN,
    PUSH_URL,
    SEQUENCE,
    SESSION_ID,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


def snapshot(**overrides) -> RemoteMediaSnapshot:
    """A playing snapshot."""
    values = {
        "server_id": "home",
        "entity_id": ENTITY_ID,
        "device_name": "Speaker",
        "state": "playing",
        "title": "First",
        "artist": "Artist",
        "album": "Album",
        "content_id": "track-1",
        "duration": 240.0,
        "position": 10.0,
        "position_updated_at_unix": 1788739200.0,
        "volume": 0.4,
        "is_muted": False,
        "features": 84037,
    }
    values.update(overrides)
    return RemoteMediaSnapshot(**values)


async def _settle(hass: HomeAssistant) -> None:
    """Let the coalescing window elapse and any send finish."""
    async_fire_time_changed(
        hass, dt_util.utcnow() + dt_util.dt.timedelta(seconds=COALESCE_SECONDS + 0.1)
    )
    await hass.async_block_till_done()


@pytest.fixture
async def publisher(hass: HomeAssistant, push_entry: ConfigEntry):
    """A publisher for a followed player, with the relay mocked to succeed."""
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    await hass.async_block_till_done()
    return async_get_manager(hass).async_add(
        WEBHOOK_ID, session(), push_entry, reconcile=False
    )


class TestMeaningfulChange:
    """What counts as worth a push."""

    def test_the_first_snapshot_always_is(self) -> None:
        """Nothing is on the card yet."""
        assert is_meaningful_change(None, snapshot())

    def test_ordinary_progress_is_not(self) -> None:
        """The expensive mistake. The card is already extrapolating between updates."""
        published = snapshot(position=10.0, position_updated_at_unix=1000.0)
        # 30 seconds later, 30 seconds further in.
        progressed = snapshot(position=40.0, position_updated_at_unix=1030.0)
        assert not is_meaningful_change(published, progressed)

    def test_progress_with_integration_rounding_is_not(self) -> None:
        """Reported positions drift by a second or two; that is not a seek."""
        published = snapshot(position=10.0, position_updated_at_unix=1000.0)
        for reported in (39.0, 40.0, 41.5, 42.9):
            drifted = snapshot(position=reported, position_updated_at_unix=1030.0)
            assert not is_meaningful_change(published, drifted), reported

    @pytest.mark.parametrize("target", [90.0, 5.0, 0.0, 200.0])
    def test_a_seek_is(self, target: float) -> None:
        """A jump playback would not have made."""
        published = snapshot(position=10.0, position_updated_at_unix=1000.0)
        seeked = snapshot(position=target, position_updated_at_unix=1030.0)
        assert is_meaningful_change(published, seeked)

    def test_a_position_change_while_paused_is(self) -> None:
        """Nothing is advancing, so any movement was a user."""
        published = snapshot(
            state="paused", position=10.0, position_updated_at_unix=1000.0
        )
        moved = snapshot(state="paused", position=60.0, position_updated_at_unix=1000.0)
        assert is_meaningful_change(published, moved)

    def test_a_track_change_is(self) -> None:
        """A different song is a different card."""
        assert is_meaningful_change(
            snapshot(), snapshot(content_id="track-2", title="Second")
        )

    @pytest.mark.parametrize("state", ["paused", "idle", "off", "unavailable"])
    def test_a_playback_transition_is(self, state: str) -> None:
        """Play, pause and stop all look different."""
        assert is_meaningful_change(snapshot(), snapshot(state=state))

    def test_buffering_is_not_a_transition_from_playing(self) -> None:
        """The card renders both as playing, so the difference is invisible."""
        assert not is_meaningful_change(
            snapshot(state="playing"), snapshot(state="buffering")
        )

    def test_a_relabelled_stop_is_not(self) -> None:
        """`idle`, `off` and `standby` all render the same; swapping them says nothing."""
        assert not is_meaningful_change(snapshot(state="idle"), snapshot(state="off"))

    def test_a_capability_change_is(self) -> None:
        """The card draws its buttons from these."""
        assert is_meaningful_change(snapshot(), snapshot(features=1))

    def test_a_meaningful_volume_change_is(self) -> None:
        """The card shows a volume slider."""
        assert is_meaningful_change(snapshot(volume=0.4), snapshot(volume=0.6))

    def test_a_negligible_volume_change_is_not(self) -> None:
        """Float noise is not a user."""
        assert not is_meaningful_change(snapshot(volume=0.4), snapshot(volume=0.405))

    def test_muting_is(self) -> None:
        """Visible on the card."""
        assert is_meaningful_change(snapshot(), snapshot(is_muted=True))

    @pytest.mark.parametrize(
        "difference",
        [
            {"server_id": "cabin"},
            {"duration": 300.0},
            {"device_name": "Kitchen speaker"},
            {"device_class": "tv"},
            {"artwork_url": "https://cdn.example.com/other.jpg"},
        ],
        ids=["server", "duration", "name", "class", "artwork"],
    )
    def test_anything_the_card_draws_is(self, difference: dict[str, Any]) -> None:
        """The card renders each of these, so a change to one of them has to be sent."""
        assert is_meaningful_change(snapshot(), snapshot(**difference))

    def test_an_identical_snapshot_is_not(self) -> None:
        """Nothing to say."""
        assert not is_meaningful_change(snapshot(), snapshot())


class TestTimestamps:
    """The outer APNs ordering clock, which Core owns."""

    def test_it_uses_wall_clock_seconds(self, freezer: FrozenDateTimeFactory) -> None:
        """A session starts with no ordering value."""
        freezer.move_to("2026-09-07 00:00:00+00:00")
        stored = session()
        assert stored.last_timestamp is None

    async def test_two_pushes_in_one_second_still_order(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """APNs sequences a session's pushes by this, and a second is a long time."""
        freezer.move_to("2026-09-07 00:00:00+00:00")
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})

        publisher.async_publish(snapshot())
        await hass.async_block_till_done()
        publisher.async_publish(snapshot(content_id="track-2", title="Second"))
        await hass.async_block_till_done()

        timestamps = [
            call[2]["now_playing"]["timestamp"] for call in aioclient_mock.mock_calls
        ]
        assert len(timestamps) == 2
        assert timestamps[1] == timestamps[0] + 1
        assert timestamps[0] == 1788739200

    async def test_a_clock_that_went_backwards_cannot_reorder(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """A corrected clock must not let an older ordering value out."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        publisher.session.last_timestamp = 1788739200
        freezer.move_to("2020-01-01 00:00:00+00:00")

        publisher.async_publish(snapshot())
        await hass.async_block_till_done()

        sent = aioclient_mock.mock_calls[0][2]["now_playing"]["timestamp"]
        assert sent == 1788739201

    async def test_ordering_survives_a_restart(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """The clock is persisted with the session."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        freezer.move_to("2020-01-01 00:00:00+00:00")
        restored = session()
        restored.last_timestamp = 1788739500
        publisher = async_get_manager(hass).async_add(
            WEBHOOK_ID, restored, push_entry, reconcile=False
        )

        publisher.async_publish(snapshot())
        await hass.async_block_till_done()
        assert aioclient_mock.mock_calls[0][2]["now_playing"]["timestamp"] == 1788739501

    async def test_sessions_have_independent_clocks(
        self, hass: HomeAssistant, push_entry: ConfigEntry
    ) -> None:
        """One session's traffic must not push another's ordering forward."""
        first = session()
        second = RemoteMediaSession(
            session_id="4:homemedia_player.other",
            generation="other",
            generation_sequence=SEQUENCE,
            entity_id="media_player.other",
            server_id="home",
            push_token=PUSH_TOKEN,
            schema_version=1,
            last_timestamp=999,
        )
        manager = async_get_manager(hass)
        manager.async_add(WEBHOOK_ID, first, push_entry, reconcile=False)
        manager.async_add(WEBHOOK_ID, second, push_entry, reconcile=False)
        assert first.last_timestamp is None
        assert second.last_timestamp == 999


class TestDelivery:
    """One sender per session, and no queue of stale requests."""

    async def test_ordinary_progress_produces_no_traffic(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """A stream of position updates from a playing track must push once, at most."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        base = 1788739200.0
        for step in range(30):
            hass.states.async_set(
                ENTITY_ID,
                "playing",
                {
                    **PLAYING_ATTRIBUTES,
                    "media_position": 10 + step * 5,
                    "media_position_updated_at": dt_util.utc_from_timestamp(
                        base + step * 5
                    ).isoformat(),
                },
            )
            await _settle(hass)

        # The first report is the card; nothing after it says anything new.
        assert len(aioclient_mock.mock_calls) == 1

    async def test_a_transient_sequence_coalesces_into_one_push(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """`playing A` -> `idle` blank -> `playing B` is one outcome, not three cards."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        hass.states.async_set(ENTITY_ID, "idle", {"friendly_name": "Speaker"})
        hass.states.async_set(
            ENTITY_ID,
            "playing",
            {
                **PLAYING_ATTRIBUTES,
                "media_content_id": "track-2",
                "media_title": "Second",
            },
        )
        await _settle(hass)

        assert len(aioclient_mock.mock_calls) == 1
        sent = aioclient_mock.mock_calls[0][2]["now_playing"]["attributes"]["snapshot"]
        assert sent["title"] == "Second"

    async def test_a_slow_relay_does_not_queue_requests(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """A burst while one send is in flight results in one more, carrying the newest state."""
        release = asyncio.Event()
        sent: list[dict[str, Any]] = []

        async def slow_relay(method, url, data):
            sent.append(data)
            await release.wait()
            return AiohttpClientMockResponse(
                method, url, status=HTTPStatus.CREATED, json={}
            )

        aioclient_mock.post(PUSH_URL, side_effect=slow_relay)

        publisher.async_publish(snapshot(title="One"))
        await asyncio.sleep(0)
        for title in ("Two", "Three", "Four"):
            publisher.async_publish(snapshot(content_id=title, title=title))
        release.set()
        await hass.async_block_till_done()

        # One in flight, then exactly one more with the newest desired state — not four.
        assert len(sent) == 2
        assert sent[1]["now_playing"]["attributes"]["snapshot"]["title"] == "Four"

    async def test_replacing_a_session_retires_its_in_flight_sender(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """A late result from an old token cannot overwrite or retry the replacement."""
        release = asyncio.Event()
        sent: list[dict[str, Any]] = []

        async def failing_relay(
            method: str, url: str, data: dict[str, Any]
        ) -> AiohttpClientMockResponse:
            sent.append(data)
            await release.wait()
            return AiohttpClientMockResponse(
                method, url, status=HTTPStatus.INTERNAL_SERVER_ERROR, json={}
            )

        aioclient_mock.post(PUSH_URL, side_effect=failing_relay)
        manager = async_get_manager(hass)
        old_session = session()
        async_save_session(hass, WEBHOOK_ID, old_session)
        old_publisher = manager.async_add(
            WEBHOOK_ID, old_session, push_entry, reconcile=False
        )
        assert old_publisher is not None
        old_publisher.async_publish(snapshot(title="Old"))
        await asyncio.sleep(0)

        replacement = session(push_token=LATER_PUSH_TOKEN)
        async_save_session(hass, WEBHOOK_ID, replacement)
        manager.async_add(WEBHOOK_ID, replacement, push_entry, reconcile=False)

        release.set()
        await hass.async_block_till_done()
        stored = hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID][SESSION_ID]
        assert stored["push_token"] == LATER_PUSH_TOKEN

        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(sent) == 1

    async def test_a_stale_completion_cannot_overwrite_newer_state(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The newest desired state is always what goes out next."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        publisher.async_publish(snapshot(title="Old"))
        publisher.async_publish(snapshot(content_id="new", title="New"))
        await hass.async_block_till_done()
        last = aioclient_mock.mock_calls[-1][2]["now_playing"]["attributes"]["snapshot"]
        assert last["title"] == "New"

    async def test_a_dead_token_removes_the_session(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The one relay answer that unregisters and detaches all runtime ownership."""
        manager = async_get_manager(hass)
        watcher = manager.watchers[ENTITY_ID]
        aioclient_mock.post(
            PUSH_URL, status=HTTPStatus.GONE, json={"errorType": "InvalidToken"}
        )
        async_save_session(hass, WEBHOOK_ID, publisher.session)
        publisher.async_publish(snapshot())
        await hass.async_block_till_done()

        # pylint: disable-next=home-assistant-use-runtime-data
        assert hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS].get(WEBHOOK_ID, {}) == {}
        assert publisher._removed
        assert manager.async_get(WEBHOOK_ID, SESSION_ID) is None
        assert ENTITY_ID not in manager.watchers
        assert watcher.publishers == {}
        assert watcher._unsubscribe is None
        assert watcher._unsubscribe_registry is None
        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]["now_playing"]["event"] == "update"

    @pytest.mark.parametrize(
        ("status", "error_type"),
        [
            (HTTPStatus.FORBIDDEN, "UnsupportedApp"),
            (HTTPStatus.BAD_REQUEST, "TopicMismatch"),
            (HTTPStatus.BAD_GATEWAY, "ProviderAuth"),
            (HTTPStatus.NOT_IMPLEMENTED, "NowPlayingNotConfigured"),
            (HTTPStatus.TOO_MANY_REQUESTS, "RateLimited"),
            (HTTPStatus.BAD_GATEWAY, "ApnsUnavailable"),
        ],
    )
    async def test_other_failures_keep_the_session(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        status: int,
        error_type: str,
    ) -> None:
        """A relay or deployment problem is not the user's session token's fault."""
        async_save_session(hass, WEBHOOK_ID, publisher.session)
        aioclient_mock.post(PUSH_URL, status=status, json={"errorType": error_type})
        publisher.async_publish(snapshot())
        await hass.async_block_till_done()

        # pylint: disable-next=home-assistant-use-runtime-data
        stored = hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID]
        assert SESSION_ID in stored

    async def test_a_misconfigured_relay_is_reported_once(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Not once per state change of a playing media player."""
        aioclient_mock.post(
            PUSH_URL, status=HTTPStatus.FORBIDDEN, json={"errorType": "UnsupportedApp"}
        )
        for index in range(5):
            publisher.async_publish(snapshot(content_id=f"track-{index}"))
            await hass.async_block_till_done()

        assert caplog.text.count("will not deliver Remote Now Playing updates") == 1
        # And it did not keep hammering the relay either.
        assert len(aioclient_mock.mock_calls) == 1

    async def test_no_token_reaches_the_log(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Neither the APNs destination nor the Companion token."""
        aioclient_mock.post(
            PUSH_URL, status=HTTPStatus.GONE, json={"errorType": "InvalidToken"}
        )
        publisher.async_publish(snapshot())
        await hass.async_block_till_done()
        assert PUSH_TOKEN not in caplog.text
        assert "COMPANION_TOKEN" not in caplog.text


class TestAnUpdateThatIsStillOwed:
    """A snapshot that failed to go out is the current state of the player just the same.

    Nothing else will re-offer it. An integration that emits a state event only when something
    changes may say nothing more until the user touches the speaker, so the retry timer is the
    only thing standing between a failed send and a card that is silently wrong.
    """

    @staticmethod
    def _relay(
        sent: list[dict[str, Any]], failures: int, release: asyncio.Event | None = None
    ):
        """A relay that refuses the first `failures` requests, then accepts."""

        async def respond(method: str, url: str, data: dict[str, Any]):
            sent.append(data)
            if release is not None and len(sent) == 1:
                await release.wait()
            status = (
                HTTPStatus.INTERNAL_SERVER_ERROR
                if len(sent) <= failures
                else HTTPStatus.CREATED
            )
            return AiohttpClientMockResponse(method, url, status=status, json={})

        return respond

    async def test_a_newer_snapshot_that_raced_a_failed_send_is_not_lost(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """The track changed while the send that failed was still in flight."""
        release = asyncio.Event()
        sent: list[dict[str, Any]] = []
        aioclient_mock.post(PUSH_URL, side_effect=self._relay(sent, 1, release))

        publisher.async_publish(snapshot(title="One"))
        await asyncio.sleep(0)
        publisher.async_publish(snapshot(content_id="two", title="Two"))
        release.set()
        await hass.async_block_till_done()
        assert len(sent) == 1, (
            "the newer snapshot must not be sent into a failing relay"
        )

        # No further state change: only the retry can carry it.
        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert len(sent) == 2
        assert sent[1]["now_playing"]["attributes"]["snapshot"]["title"] == "Two"

    async def test_returning_to_the_published_state_supersedes_a_failed_update(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """A failed B is no longer owed after the entity settles back at published A."""
        sent: list[dict[str, Any]] = []

        async def relay(
            method: str, url: str, data: dict[str, Any]
        ) -> AiohttpClientMockResponse:
            sent.append(data)
            status = HTTPStatus.CREATED if len(sent) == 1 else HTTPStatus.BAD_GATEWAY
            return AiohttpClientMockResponse(method, url, status=status, json={})

        aioclient_mock.post(PUSH_URL, side_effect=relay)

        publisher.async_apply(snapshot())
        await _settle(hass)
        publisher.async_apply(snapshot(content_id="track-2", title="Second"))
        await _settle(hass)
        publisher.async_apply(snapshot())
        await _settle(hass)

        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert len(sent) == 2
        assert sent[0]["now_playing"]["attributes"]["snapshot"]["title"] == "First"
        assert sent[1]["now_playing"]["attributes"]["snapshot"]["title"] == "Second"

    async def test_a_send_that_raises_is_retried_rather_than_discarded(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An exception on the way out says nothing about whether the snapshot is current."""
        sent: list[dict[str, Any]] = []

        async def erratic(method: str, url: str, data: dict[str, Any]):
            sent.append(data)
            if len(sent) == 1:
                raise ValueError("the request came apart")
            return AiohttpClientMockResponse(
                method, url, status=HTTPStatus.CREATED, json={}
            )

        aioclient_mock.post(PUSH_URL, side_effect=erratic)
        publisher.async_publish(snapshot(title="One"))
        await hass.async_block_till_done()
        assert "Could not send a Remote Now Playing update" in caplog.text

        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert len(sent) == 2
        assert sent[1]["now_playing"]["attributes"]["snapshot"]["title"] == "One"

    async def test_the_delay_doubles_while_it_keeps_failing(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """One timer at a time, each further out than the last, and never a poll."""
        sent: list[dict[str, Any]] = []
        aioclient_mock.post(PUSH_URL, side_effect=self._relay(sent, 3))

        publisher.async_publish(snapshot(title="One"))
        await hass.async_block_till_done()
        assert len(sent) == 1

        # Just short of each expected delay nothing happens; just past it, exactly one attempt.
        for expected in (RETRY_BACKOFF_SECONDS, RETRY_BACKOFF_SECONDS * 2):
            attempts = len(sent)
            freezer.tick(dt_util.dt.timedelta(seconds=expected - 1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert len(sent) == attempts, f"retried before {expected}s had passed"

            freezer.tick(dt_util.dt.timedelta(seconds=2))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert len(sent) == attempts + 1

    async def test_the_delay_is_capped(self) -> None:
        """A session that has been failing for a day must not wait a week."""
        assert MAXIMUM_RETRY_BACKOFF_SECONDS == 900

    async def test_ending_the_session_cancels_the_retry(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Nothing may fire for a relationship that is over."""
        sent: list[dict[str, Any]] = []
        aioclient_mock.post(PUSH_URL, side_effect=self._relay(sent, 99))

        publisher.async_publish(snapshot(title="One"))
        await hass.async_block_till_done()
        assert len(sent) == 1

        async_get_manager(hass).async_end_session(WEBHOOK_ID, SESSION_ID)
        await hass.async_block_till_done()
        after_end = len(sent)

        freezer.tick(dt_util.dt.timedelta(seconds=MAXIMUM_RETRY_BACKOFF_SECONDS * 2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(sent) == after_end, "a removed session must not keep retrying"

    async def test_a_delivery_resets_the_delay(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Or a session that once had a bad day would stay slow to recover forever."""
        sent: list[dict[str, Any]] = []
        aioclient_mock.post(PUSH_URL, side_effect=self._relay(sent, 1))

        publisher.async_publish(snapshot(title="One"))
        await hass.async_block_till_done()
        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(sent) == 2, "the retry should have landed"

        # Failing again starts from the base delay rather than from where it left off.
        aioclient_mock.clear_requests()
        sent.clear()
        aioclient_mock.post(PUSH_URL, side_effect=self._relay(sent, 1))
        publisher.async_publish(snapshot(content_id="two", title="Two"))
        await hass.async_block_till_done()
        assert len(sent) == 1

        freezer.tick(dt_util.dt.timedelta(seconds=RETRY_BACKOFF_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(sent) == 2


class TestInitialSynchronisation:
    """What happens the moment a Follow relationship is registered."""

    async def test_a_new_registration_publishes_the_current_state_once(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The card is brought up to date immediately, which also proves the token."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        await hass.async_block_till_done()

        async_get_manager(hass).async_add(
            WEBHOOK_ID, session(), push_entry, reconcile=True
        )
        await _settle(hass)

        assert len(aioclient_mock.mock_calls) == 1
        body = aioclient_mock.mock_calls[0][2]
        assert body["now_playing"]["event"] == "update"
        attributes = body["now_playing"]["attributes"]
        assert attributes["id"] == SESSION_ID
        assert attributes["generation"] == GENERATION
        assert attributes["snapshot"]["title"] == "First"

    async def test_a_player_with_nothing_playing_publishes_nothing(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """No track is invented; the relationship waits for something meaningful."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        hass.states.async_set(ENTITY_ID, "idle", {"friendly_name": "Speaker"})
        await hass.async_block_till_done()

        async_get_manager(hass).async_add(
            WEBHOOK_ID, session(), push_entry, reconcile=True
        )
        await _settle(hass)

        assert len(aioclient_mock.mock_calls) == 0
        # Still following, still listening.
        assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is not None

    async def test_a_restored_session_does_not_re_push_what_the_card_shows(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """A restart must not wake every phone whose player has not changed."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        await hass.async_block_till_done()

        restored = session()
        restored.last_snapshot = snapshot()
        restored.last_timestamp = 1788739200
        async_get_manager(hass).async_add(
            WEBHOOK_ID, restored, push_entry, reconcile=True
        )
        await _settle(hass)

        assert len(aioclient_mock.mock_calls) == 0


class TestLifecycle:
    """Listeners, sharing and removal."""

    async def test_sessions_on_the_same_player_share_one_listener(
        self, hass: HomeAssistant, push_entry: ConfigEntry
    ) -> None:
        """Two devices can follow the same speaker."""
        manager = async_get_manager(hass)
        first = session()
        second = session()
        second.session_id = "4:homemedia_player.speaker#2"
        manager.async_add(WEBHOOK_ID, first, push_entry, reconcile=False)
        manager.async_add(WEBHOOK_ID, second, push_entry, reconcile=False)

        assert len(manager.watchers) == 1
        assert len(manager.watchers[ENTITY_ID].publishers) == 2

    async def test_removing_one_keeps_the_listener_for_the_other(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The listener goes only when the last session following the player does."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        manager = async_get_manager(hass)
        first = session()
        second = session()
        second.session_id = "4:homemedia_player.speaker#2"
        manager.async_add(WEBHOOK_ID, first, push_entry, reconcile=False)
        manager.async_add(WEBHOOK_ID, second, push_entry, reconcile=False)

        manager.async_end_session(WEBHOOK_ID, first.session_id)
        await hass.async_block_till_done()
        assert ENTITY_ID in manager.watchers
        manager.async_end_session(WEBHOOK_ID, second.session_id)
        await hass.async_block_till_done()
        assert ENTITY_ID not in manager.watchers

    async def test_a_state_disappearance_never_ends_following(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """`new_state is None` says nothing durable.

        An integration reload, a platform reload and startup ordering all produce it, and there is
        no length of time that separates those from a deletion — so no amount of waiting is used.
        """
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        async_save_session(hass, WEBHOOK_ID, publisher.session)

        hass.states.async_remove(ENTITY_ID)
        await hass.async_block_till_done()
        # However long it stays gone.
        async_fire_time_changed(hass, dt_util.utcnow() + dt_util.dt.timedelta(hours=6))
        await hass.async_block_till_done()

        assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is not None
        assert SESSION_ID in hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID]
        # And nothing was sent about it.
        assert not [
            call
            for call in aioclient_mock.mock_calls
            if call[2]["now_playing"]["event"] == "end"
        ]

    async def test_an_entity_that_comes_back_resumes(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The card picks up where the player did."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        async_save_session(hass, WEBHOOK_ID, publisher.session)

        hass.states.async_remove(ENTITY_ID)
        await hass.async_block_till_done()
        hass.states.async_set(
            ENTITY_ID, "playing", {**PLAYING_ATTRIBUTES, "media_title": "Second"}
        )
        await _settle(hass)

        assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is not None
        titles = [
            call[2]["now_playing"]["attributes"]["snapshot"].get("title")
            for call in aioclient_mock.mock_calls
        ]
        assert "Second" in titles

    async def test_a_registry_removal_ends_following(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        entity_registry: er.EntityRegistry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The registry is where permanence is decided, so this is the signal that ends it."""
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        entry = entity_registry.async_get_or_create(
            "media_player", "demo", "unique-1", suggested_object_id="speaker"
        )
        assert entry.entity_id == ENTITY_ID
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        await hass.async_block_till_done()
        manager = async_get_manager(hass)
        manager.async_add(WEBHOOK_ID, session(), push_entry, reconcile=False)
        async_save_session(hass, WEBHOOK_ID, session())

        entity_registry.async_remove(ENTITY_ID)
        await hass.async_block_till_done()

        assert manager.async_get(WEBHOOK_ID, SESSION_ID) is None
        assert ENTITY_ID not in manager.watchers
        assert hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS].get(WEBHOOK_ID, {}) == {}
        # Best effort told the phone.
        assert [
            call
            for call in aioclient_mock.mock_calls
            if call[2]["now_playing"]["event"] == "end"
        ]

    async def test_a_registry_rename_moves_the_relationship(
        self,
        hass: HomeAssistant,
        push_entry: ConfigEntry,
        entity_registry: er.EntityRegistry,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """The relationship is with the player, not with its name.

        Its identifier, its place in the order and its token all describe the Follow, none of them
        the entity id — so a rename must not break it, and must not look like a new relationship.
        """
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        entity_registry.async_get_or_create(
            "media_player", "demo", "unique-1", suggested_object_id="speaker"
        )
        hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
        await hass.async_block_till_done()
        manager = async_get_manager(hass)
        stored = session()
        manager.async_add(WEBHOOK_ID, stored, push_entry, reconcile=True)
        await _settle(hass)

        renamed = "media_player.living_room"
        entity_registry.async_update_entity(ENTITY_ID, new_entity_id=renamed)
        hass.states.async_set(renamed, "playing", PLAYING_ATTRIBUTES)
        await _settle(hass)

        publisher = manager.async_get(WEBHOOK_ID, SESSION_ID)
        assert publisher is not None
        assert publisher.session.entity_id == renamed
        # Untouched by the rename.
        assert publisher.session.session_id == SESSION_ID
        assert publisher.session.generation == GENERATION
        assert publisher.session.generation_sequence == SEQUENCE
        assert publisher.session.push_token == PUSH_TOKEN
        # The listener moved with it.
        assert renamed in manager.watchers
        assert ENTITY_ID not in manager.watchers
        assert (
            hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS][WEBHOOK_ID][SESSION_ID][
                "entity_id"
            ]
            == renamed
        )
        # And the phone was told, because the card issues commands against the selection.
        selections = [
            call[2]["now_playing"]["attributes"]["snapshot"]["selection"]["entityId"]
            for call in aioclient_mock.mock_calls
            if "snapshot" in call[2]["now_playing"]["attributes"]
        ]
        assert selections[-1] == renamed

    async def test_an_entity_with_no_registry_entry_stays_dormant(
        self,
        hass: HomeAssistant,
        publisher,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Some entities have no registry entry, so there is no removal signal to wait for.

        Rather than invent another timeout, the relationship simply stays. Stop Following,
        config-entry removal and an `InvalidToken` from APNs all still clean it up.
        """
        aioclient_mock.post(PUSH_URL, status=HTTPStatus.CREATED, json={})
        async_save_session(hass, WEBHOOK_ID, publisher.session)
        assert hass.states.get(ENTITY_ID) is not None

        hass.states.async_remove(ENTITY_ID)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + dt_util.dt.timedelta(days=1))
        await hass.async_block_till_done()

        assert async_get_manager(hass).async_get(WEBHOOK_ID, SESSION_ID) is not None


class TestCloudPushCapability:
    """A registration Core cannot reach is remembered rather than watched.

    Entering through the webhook is covered in `test_webhook.py`; this is the manager's own view.
    """

    async def test_a_dormant_relationship_can_still_be_stopped(
        self, hass: HomeAssistant, local_only_entry: ConfigEntry
    ) -> None:
        """Stop Following works whether or not anything was ever watched."""
        manager = async_get_manager(hass)
        manager.async_add(WEBHOOK_ID, session(), local_only_entry, reconcile=False)
        async_save_session(hass, WEBHOOK_ID, session())

        manager.async_end_session(WEBHOOK_ID, SESSION_ID)
        await hass.async_block_till_done()

        assert not manager.async_is_known(WEBHOOK_ID, SESSION_ID)
        assert hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS].get(WEBHOOK_ID, {}) == {}
