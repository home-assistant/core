"""Tests for the mobile_app Live Activity webhook handlers."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.mobile_app.const import (
    DATA_LIVE_ACTIVITY_PENDING_UPDATES,
    DATA_LIVE_ACTIVITY_TOKENS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, MockUser, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_webhook_update_live_activity_token(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that we can store a Live Activity push token."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = create_registrations[1]["webhook_id"]
    expires_at = dt_util.utcnow().timestamp() + 3600
    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "expires_at": expires_at,
            },
        },
    )

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {}

    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    assert tokens == {
        webhook_id: {
            "washer_cycle": {
                "token": (
                    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
                ),
                "expires_at": expires_at,
            },
        },
    }


async def test_webhook_ignores_out_of_order_older_token(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale token delivered out of order does not overwrite a newer one."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = create_registrations[1]["webhook_id"]
    newer_expires_at = dt_util.utcnow().timestamp() + 3600

    # The newer token (later expiry) arrives first.
    await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "b" * 64,
                "expires_at": newer_expires_at,
            },
        },
    )

    # A stale token for the same tag (earlier expiry) is delivered late and must be ignored.
    await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a" * 64,
                "expires_at": dt_util.utcnow().timestamp() + 60,
            },
        },
    )

    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS] == {
        webhook_id: {
            "washer_cycle": {"token": "b" * 64, "expires_at": newer_expires_at},
        },
    }


async def test_webhook_live_activity_token_schedules_cleanup(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that storing the first token schedules a cleanup that expires it."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = create_registrations[1]["webhook_id"]
    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    expires_at = dt_util.utcnow().timestamp() + 60
    # No tokens yet, and no cleanup scheduled
    assert tokens == {}

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "expires_at": expires_at,
            },
        },
    )
    assert resp.status == HTTPStatus.OK

    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    assert tokens == {
        webhook_id: {
            "washer_cycle": {
                "token": (
                    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
                ),
                "expires_at": expires_at,
            },
        },
    }

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert tokens == {}


async def test_webhook_live_activity_token_cleanup_reschedules_for_remaining(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cleanup reschedules itself when some tokens remain after a sweep."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = create_registrations[1]["webhook_id"]
    first_expires_at = dt_util.utcnow().timestamp() + 60

    # First token at t=0, expires in 60 seconds.
    await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "first",
                "push_token": "a" * 64,
                "expires_at": first_expires_at,
            },
        },
    )

    # Advance halfway to the first expiry, then store a second token. Its expiry
    # is later than the first's, so the initial cleanup sweep should remove only
    # the first and reschedule itself for the second's expiry.
    freezer.tick(timedelta(seconds=30))
    second_expires_at = dt_util.utcnow().timestamp() + 60
    await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "second",
                "push_token": "b" * 64,
                "expires_at": second_expires_at,
            },
        },
    )

    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    assert tokens == {
        webhook_id: {
            "first": {"token": "a" * 64, "expires_at": first_expires_at},
            "second": {"token": "b" * 64, "expires_at": second_expires_at},
        },
    }

    # Fire just past the first token's expiry. The originally scheduled sweep
    # runs, removes the first token, and reschedules itself for the second.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert tokens == {
        webhook_id: {
            "second": {"token": "b" * 64, "expires_at": second_expires_at},
        },
    }

    # Fire past the second token's expiry. The rescheduled sweep should run
    # and remove the second token, draining the store.
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert tokens == {}


async def test_webhook_live_activity_dismissed(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that we can dismiss a Live Activity and clean up its token."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = create_registrations[1]["webhook_id"]
    expires_at = dt_util.utcnow().timestamp() + 3600

    # First register a token
    await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "expires_at": expires_at,
            },
        },
    )

    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    assert tokens == {
        webhook_id: {
            "washer_cycle": {
                "token": (
                    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
                ),
                "expires_at": expires_at,
            },
        },
    }

    # Now dismiss it
    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_dismissed",
            "data": {
                "tag": "washer_cycle",
            },
        },
    )

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {}

    # webhook_id key also cleaned up since no activities remain
    assert tokens == {}


async def test_webhook_live_activity_dismissed_nonexistent_tag(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that dismissing a nonexistent tag does not error."""
    webhook_id = create_registrations[1]["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_dismissed",
            "data": {
                "tag": "nonexistent_activity",
            },
        },
    )

    assert resp.status == HTTPStatus.OK
    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS] == {}


async def test_webhook_token_flushes_buffered_update(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
    webhook_client: TestClient,
) -> None:
    """Test reporting the token flushes the buffered latest update as an update."""
    push_url = "https://mobile-push.home-assistant.dev/push"
    now = dt_util.naive_now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "successful": 1,
                "errors": 0,
                "maximum": 150,
                "resetsAt": iso_time,
            }
        },
    )

    entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "FCM_TOKEN",
                "push_url": push_url,
                "start_live_activity_token": "PUSH_TO_START_HEX_TOKEN",
                "live_activity_start_failsafe": 21600,
            },
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2024.1",
            "device_id": "ios-device-1",
            "device_name": "iPhone",
            "manufacturer": "Apple",
            "model": "iPhone 15",
            "os_name": "iOS",
            "os_version": "17.2",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "ios-webhook-1",
        },
        domain=DOMAIN,
        source="registration",
        title="iPhone entry",
        version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start, then a fresher update that is buffered while no token is known.
    for progress in (10, 90):
        await hass.services.async_call(
            "notify",
            "mobile_app_iphone",
            {
                "message": "Laundry running",
                "target": ["ios-webhook-1"],
                "data": {"live_update": True, "tag": "laundry", "progress": progress},
            },
            blocking=True,
        )
    assert len(aioclient_mock.mock_calls) == 1

    expires_at = dt_util.utcnow().timestamp() + 3600
    resp = await webhook_client.post(
        "/api/webhook/ios-webhook-1",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "laundry",
                "push_token": "PER_ACTIVITY_TOKEN",
                "expires_at": expires_at,
            },
        },
    )
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 2
    flushed = aioclient_mock.mock_calls[1][2]
    assert flushed["live_activity_token"] == "PER_ACTIVITY_TOKEN"
    assert flushed["data"] == {
        "live_update": True,
        "tag": "laundry",
        "progress": 90,
        "event": "update",
    }
    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_UPDATES] == {}
