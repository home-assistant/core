"""Tests for the mobile_app Live Activity webhook handlers."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.mobile_app.const import DATA_LIVE_ACTIVITY_TOKENS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


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
