"""Live tests for the Elke27 integration."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    CONF_PIN,
    DATA_COORDINATOR,
    DATA_HUB,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _load_live_config() -> tuple[str, int, dict[str, str], str, str | None]:
    host = os.environ.get("ELKE27_LIVE_HOST")
    link_keys_raw = os.environ.get("ELKE27_LIVE_LINK_KEYS")
    if not host or not link_keys_raw:
        pytest.skip("Set ELKE27_LIVE_HOST and ELKE27_LIVE_LINK_KEYS to run live tests")
    port = int(os.environ.get("ELKE27_LIVE_PORT", DEFAULT_PORT))
    link_keys_json = json.loads(link_keys_raw)
    integration_serial = os.environ.get("ELKE27_LIVE_INTEGRATION_SERIAL", "live")
    pin = os.environ.get("ELKE27_LIVE_PIN")
    return host, port, link_keys_json, integration_serial, pin


def _get_zone_bypassed(snapshot: object | None, zone_id: int) -> bool | None:
    if snapshot is None:
        return None
    zones = getattr(snapshot, "zones", None)
    if zones is None:
        return None
    if isinstance(zones, dict):
        zone = zones.get(zone_id)
        return getattr(zone, "bypassed", None) if zone is not None else None
    for zone in zones:
        if getattr(zone, "zone_id", None) == zone_id:
            return getattr(zone, "bypassed", None)
    return None


async def _wait_for_bypass_state(
    coordinator: object, zone_id: int, expected: bool, timeout: float
) -> None:
    event = asyncio.Event()

    def _check() -> None:
        if _get_zone_bypassed(getattr(coordinator, "data", None), zone_id) is expected:
            event.set()

    remove = coordinator.async_add_listener(_check)
    try:
        _check()
        await asyncio.wait_for(event.wait(), timeout=timeout)
    finally:
        remove()


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("ELKE27_LIVE") != "1",
    reason="Set ELKE27_LIVE=1 to run live Elke27 tests",
)
async def test_live_setup_and_snapshot(hass: HomeAssistant) -> None:
    """Verify live setup populates coordinator data."""
    host, port, link_keys_json, integration_serial, pin = _load_live_config()
    data = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_LINK_KEYS_JSON: link_keys_json,
        CONF_INTEGRATION_SERIAL: integration_serial,
    }
    if pin:
        data[CONF_PIN] = pin

    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    assert coordinator.data is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("ELKE27_LIVE") != "1",
    reason="Set ELKE27_LIVE=1 to run live Elke27 tests",
)
async def test_live_zone_bypass_events(hass: HomeAssistant) -> None:
    """Verify bypass/unbypass events update coordinator data."""
    host, port, link_keys_json, integration_serial, pin = _load_live_config()
    zone_id_raw = os.environ.get("ELKE27_LIVE_ZONE_ID")
    if not zone_id_raw:
        pytest.skip("Set ELKE27_LIVE_ZONE_ID to run zone bypass live test")
    if os.environ.get("ELKE27_LIVE_BYPASS_TOGGLE") != "1":
        pytest.skip("Set ELKE27_LIVE_BYPASS_TOGGLE=1 to allow bypass toggles")
    if not pin:
        pytest.skip("Set ELKE27_LIVE_PIN to run zone bypass live test")

    zone_id = int(zone_id_raw)
    timeout_s = float(os.environ.get("ELKE27_LIVE_EVENT_TIMEOUT", "30"))

    data = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_LINK_KEYS_JSON: link_keys_json,
        CONF_INTEGRATION_SERIAL: integration_serial,
        CONF_PIN: pin,
    }

    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    initial = _get_zone_bypassed(coordinator.data, zone_id)
    if initial is None:
        await hass.config_entries.async_unload(entry.entry_id)
        pytest.skip("Zone not present in snapshot or bypass state unavailable")

    target = not initial
    try:
        await hub.async_set_zone_bypass(zone_id, target)
        await _wait_for_bypass_state(coordinator, zone_id, target, timeout_s)
        await hub.async_set_zone_bypass(zone_id, initial)
        await _wait_for_bypass_state(coordinator, zone_id, initial, timeout_s)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
