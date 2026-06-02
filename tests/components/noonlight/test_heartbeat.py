"""Idle-heartbeat tests: proactively detect a bad token / unreachable API."""

from __future__ import annotations

from datetime import timedelta

import httpx
from httpx import Response
import respx

from homeassistant.components.noonlight.const import (
    DOMAIN,
    HEARTBEAT_FAILURE_THRESHOLD,
    ISSUE_AUTH_FAILED,
    ISSUE_NETWORK_FAILED,
    ISSUE_UNEXPECTED_RESPONSE,
    POLL_INTERVAL,
    STATE_IDLE,
)
from homeassistant.helpers import issue_registry as ir

from tests.common import async_fire_time_changed

_STATUS_RE = r".*/dispatch/v1/alarms/.*/status"


def _coordinator(hass, entry):
    return hass.data[DOMAIN][entry.entry_id]


def _force_due(coordinator):
    """Make the next idle refresh run a heartbeat probe."""
    coordinator._last_heartbeat = 0.0


def _has_issue(hass, key, entry_id) -> bool:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{key}_{entry_id}") is not None


@respx.mock
async def test_setup_does_not_probe_immediately(hass, setup_entry):
    """Setup must not fire a heartbeat (clock starts at creation)."""
    probe = respx.get(url__regex=_STATUS_RE).mock(return_value=Response(404))
    coordinator = _coordinator(hass, setup_entry)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not probe.called
    assert coordinator.data["api_healthy"] is True


@respx.mock
async def test_heartbeat_success_marks_healthy(hass, setup_entry):
    # 404 on the bogus probe id == reachable + authorized.
    probe = respx.get(url__regex=_STATUS_RE).mock(return_value=Response(404))
    coordinator = _coordinator(hass, setup_entry)
    _force_due(coordinator)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert probe.called
    assert coordinator.data["api_healthy"] is True
    assert coordinator.data["last_health_check"] is not None
    assert coordinator.data["state"] == STATE_IDLE
    # The reachable binary_sensor reflects health.
    assert hass.states.get("binary_sensor.noonlight_main_api_reachable").state == "on"


@respx.mock
async def test_heartbeat_5xx_outage_is_unhealthy(hass, setup_entry):
    """A 5xx outage must NOT be classified as reachable (only a 404 is)."""
    respx.get(url__regex=_STATUS_RE).mock(return_value=Response(503))
    coordinator = _coordinator(hass, setup_entry)

    for _ in range(HEARTBEAT_FAILURE_THRESHOLD):
        _force_due(coordinator)
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.data["api_healthy"] is False
    assert _has_issue(hass, ISSUE_UNEXPECTED_RESPONSE, setup_entry.entry_id)
    assert hass.states.get("binary_sensor.noonlight_main_api_reachable").state == "off"


@respx.mock
async def test_heartbeat_fires_on_real_update_timer(hass, setup_entry, freezer):
    """The probe fires via the coordinator's real refresh timer (not a
    hand-forced async_refresh), proving the scheduling wiring works.
    """
    probe = respx.get(url__regex=_STATUS_RE).mock(return_value=Response(404))
    coordinator = _coordinator(hass, setup_entry)
    assert not probe.called  # setup itself does not probe

    # Advance real (frozen) time so the seed makes the first probe due and the
    # coordinator's scheduled refresh actually fires.
    freezer.tick(timedelta(seconds=POLL_INTERVAL + 5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert probe.called
    assert coordinator.data["api_healthy"] is True
    assert coordinator.data["last_health_check"] is not None


@respx.mock
async def test_heartbeat_auth_failure_raises_issue_after_threshold(hass, setup_entry):
    respx.get(url__regex=_STATUS_RE).mock(return_value=Response(401))
    coordinator = _coordinator(hass, setup_entry)

    # First failures stay quiet (below the threshold).
    for _ in range(HEARTBEAT_FAILURE_THRESHOLD - 1):
        _force_due(coordinator)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert not _has_issue(hass, ISSUE_AUTH_FAILED, setup_entry.entry_id)
    assert coordinator.data["api_healthy"] is True

    # Crossing the threshold raises the auth issue + reauth, marks unhealthy.
    _force_due(coordinator)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data["api_healthy"] is False
    assert _has_issue(hass, ISSUE_AUTH_FAILED, setup_entry.entry_id)
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"].get("source") == "reauth" for f in flows)
    assert hass.states.get("binary_sensor.noonlight_main_api_reachable").state == "off"


@respx.mock
async def test_heartbeat_recovers_and_clears_issue(hass, setup_entry):
    coordinator = _coordinator(hass, setup_entry)
    # Drive it unhealthy via connection failures past the threshold.
    respx.get(url__regex=_STATUS_RE).mock(side_effect=httpx.ConnectError("x"))
    for _ in range(HEARTBEAT_FAILURE_THRESHOLD):
        _force_due(coordinator)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert _has_issue(hass, ISSUE_NETWORK_FAILED, setup_entry.entry_id)
    assert coordinator.data["api_healthy"] is False

    # Now it recovers: issue cleared, healthy again, failure count reset.
    respx.get(url__regex=_STATUS_RE).mock(return_value=Response(404))
    _force_due(coordinator)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data["api_healthy"] is True
    assert not _has_issue(hass, ISSUE_NETWORK_FAILED, setup_entry.entry_id)
    assert coordinator._heartbeat_failures == 0
