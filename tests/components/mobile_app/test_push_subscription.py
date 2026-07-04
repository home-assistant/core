"""Tests for mobile_app push subscriptions."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.mobile_app.const import (
    DATA_PUSH_SUBSCRIPTION_DEBOUNCE,
    DATA_PUSH_SUBSCRIPTION_UNSUBS,
    DATA_PUSH_SUBSCRIPTIONS,
    DOMAIN,
    PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS,
    PUSH_SUBSCRIPTION_ENTITY_IDS,
    PUSH_SUBSCRIPTION_ID,
    PUSH_SUBSCRIPTION_TARGET,
    PUSH_SUBSCRIPTION_TOKEN,
    PUSH_SUBSCRIPTION_TRIGGER,
)
from homeassistant.components.mobile_app.push_subscription.notify import (
    _send_subscription_push,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import REGISTER_CLEARTEXT

from tests.common import async_fire_time_changed

PUSH_URL = "https://mobile-push.home-assistant.dev/push"
TRACKED_ENTITY = "light.living_room"
SUB_ID = "sub-1"
SUB_TOKEN = "push-token-abc"

# Patch target for the inner coroutine that performs the HTTP POST, letting the
# debounce/scheduling logic run under test while the network call is stubbed.
SEND_PUSH = (
    "homeassistant.components.mobile_app.push_subscription"
    ".notify._send_subscription_push"
)
# async_get_clientsession as looked up inside notify.py - patched in the two
# direct _send_subscription_push tests so the POST never touches the network.
GET_SESSION = (
    "homeassistant.components.mobile_app.push_subscription"
    ".notify.async_get_clientsession"
)


def _mock_session_post(
    *, status: HTTPStatus | None = None, side_effect: type[Exception] | None = None
) -> MagicMock:
    """Return a session whose .post() behaves as an async context manager.

    Mirrors aiohttp's ClientSession.post, which returns a context manager the
    caller enters with ``async with`` to obtain (and later release) the response.
    """
    cm = MagicMock()
    if side_effect is not None:
        cm.__aenter__ = AsyncMock(side_effect=side_effect)
    else:
        response = MagicMock()
        response.status = status
        cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post = MagicMock(return_value=cm)
    return session


@pytest.fixture
async def push_webhook_id(hass: HomeAssistant, webhook_client: TestClient) -> str:
    """Register a cleartext, push-enabled device and return its webhook_id."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    resp = await webhook_client.post(
        "/api/mobile_app/registrations",
        json={
            **REGISTER_CLEARTEXT,
            "app_data": {"push_url": PUSH_URL, "push_token": "device-token"},
        },
    )
    assert resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()
    return (await resp.json())[CONF_WEBHOOK_ID]


async def _register_subscription(
    client: TestClient,
    webhook_id: str,
    *,
    sub_id: str = SUB_ID,
    token: str = SUB_TOKEN,
    entity_ids: list[str] | None = None,
    target: str | None = "lock_screen",
) -> None:
    """POST a register_push_subscription webhook command."""
    data: dict[str, Any] = {
        "subscription_id": sub_id,
        "push_token": token,
        "entity_ids": entity_ids or [TRACKED_ENTITY],
    }
    if target is not None:
        data["target"] = target
    resp = await client.post(
        f"/api/webhook/{webhook_id}",
        json={"type": "register_push_subscription", "data": data},
    )
    assert resp.status == HTTPStatus.OK


async def test_register_stores_subscription(
    hass: HomeAssistant, webhook_client: TestClient, push_webhook_id: str
) -> None:
    """Registering a subscription persists the mapping and arms a listener."""
    await _register_subscription(webhook_client, push_webhook_id)

    stored = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id][SUB_ID]
    assert stored[PUSH_SUBSCRIPTION_TOKEN] == SUB_TOKEN
    assert stored[PUSH_SUBSCRIPTION_ENTITY_IDS] == [TRACKED_ENTITY]
    assert stored[PUSH_SUBSCRIPTION_TARGET] == "lock_screen"
    assert SUB_ID in hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_UNSUBS][push_webhook_id]


async def test_register_is_idempotent(
    hass: HomeAssistant, webhook_client: TestClient, push_webhook_id: str
) -> None:
    """Re-registering the same id updates token/entities in place."""
    await _register_subscription(webhook_client, push_webhook_id)
    await _register_subscription(
        webhook_client,
        push_webhook_id,
        token="rotated-token",
        entity_ids=["switch.fan"],
    )

    device_subs = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id]
    assert len(device_subs) == 1
    assert device_subs[SUB_ID][PUSH_SUBSCRIPTION_TOKEN] == "rotated-token"
    assert device_subs[SUB_ID][PUSH_SUBSCRIPTION_ENTITY_IDS] == ["switch.fan"]


async def test_register_dedupes_entity_ids(
    hass: HomeAssistant, webhook_client: TestClient, push_webhook_id: str
) -> None:
    """Duplicate entity_ids collapse so a listener is not armed twice."""
    await _register_subscription(
        webhook_client,
        push_webhook_id,
        entity_ids=[TRACKED_ENTITY, TRACKED_ENTITY, "switch.fan"],
    )

    stored = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id][SUB_ID]
    assert stored[PUSH_SUBSCRIPTION_ENTITY_IDS] == [TRACKED_ENTITY, "switch.fan"]


async def test_state_change_sends_push_after_debounce(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A state change sends exactly one silent push after the debounce window."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        hass.states.async_set(TRACKED_ENTITY, "on")
        await hass.async_block_till_done()
        # Nothing sent yet - still inside the debounce window.
        assert mock_send.call_count == 0

        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 1
    # _send_subscription_push(hass, entry, sub_id, sub)
    _, _, sub_id, sub = mock_send.call_args.args
    assert sub_id == SUB_ID
    assert sub[PUSH_SUBSCRIPTION_TOKEN] == SUB_TOKEN
    assert sub[PUSH_SUBSCRIPTION_TARGET] == "lock_screen"


async def test_burst_collapses_to_single_push(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A burst of changes within the window collapses to one push."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        for i in range(5):
            hass.states.async_set(TRACKED_ENTITY, f"level-{i}")
            await hass.async_block_till_done()
            freezer.tick(timedelta(seconds=1))  # < window, restarts the clock
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        assert mock_send.call_count == 0

        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 1


async def test_separated_changes_send_separate_pushes(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two changes spaced beyond the window send two pushes."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        for value in ("on", "off"):
            hass.states.async_set(TRACKED_ENTITY, value)
            await hass.async_block_till_done()
            freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 2


async def test_untracked_entity_does_not_push(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A change to an entity not in the subscription sends nothing."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        hass.states.async_set("sensor.unrelated", "123")
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 0


async def test_remove_subscription(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Removing a subscription stops pushes and clears the mapping."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    resp = await webhook_client.post(
        f"/api/webhook/{push_webhook_id}",
        json={
            "type": "remove_push_subscription",
            "data": {"subscription_id": SUB_ID},
        },
    )
    assert resp.status == HTTPStatus.OK
    assert push_webhook_id not in hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS]

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        hass.states.async_set(TRACKED_ENTITY, "on")
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 0


async def test_pending_push_cancelled_on_unload(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading the entry cancels an in-flight debounce timer."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    hass.states.async_set(TRACKED_ENTITY, "on")
    await hass.async_block_till_done()
    # A debounce timer is pending.
    assert push_webhook_id in hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE]

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 0


async def test_subscription_restored_after_reload(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A stored subscription survives an entry reload and still pushes."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await _register_subscription(webhook_client, push_webhook_id)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # Mapping persisted and listener re-armed.
    assert SUB_ID in hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id]

    with patch(SEND_PUSH, new_callable=AsyncMock) as mock_send:
        hass.states.async_set(TRACKED_ENTITY, "on")
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_send.call_count == 1


async def test_send_push_posts_payload(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
) -> None:
    """The push POST carries the token, trigger marker and registration info."""
    await _register_subscription(webhook_client, push_webhook_id)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    sub = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id][SUB_ID]

    session = _mock_session_post(status=HTTPStatus.CREATED)

    with patch(GET_SESSION, return_value=session):
        await _send_subscription_push(hass, entry, SUB_ID, sub)

    assert session.post.call_count == 1
    url = session.post.call_args.args[0]
    payload = session.post.call_args.kwargs["json"]
    assert url == PUSH_URL
    assert payload[PUSH_SUBSCRIPTION_TOKEN] == SUB_TOKEN
    assert payload[PUSH_SUBSCRIPTION_TRIGGER][PUSH_SUBSCRIPTION_ID] == SUB_ID
    assert payload[PUSH_SUBSCRIPTION_TRIGGER][PUSH_SUBSCRIPTION_TARGET] == "lock_screen"
    assert payload["registration_info"]["webhook_id"] == push_webhook_id


async def test_send_push_swallows_client_error(
    hass: HomeAssistant,
    webhook_client: TestClient,
    push_webhook_id: str,
) -> None:
    """A transport error is swallowed - silent pushes are best-effort."""
    await _register_subscription(webhook_client, push_webhook_id)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    sub = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS][push_webhook_id][SUB_ID]

    session = _mock_session_post(side_effect=ClientError)

    with patch(GET_SESSION, return_value=session):
        # Must not raise.
        await _send_subscription_push(hass, entry, SUB_ID, sub)

    assert session.post.call_count == 1
