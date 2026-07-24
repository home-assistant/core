"""Tests for iTach IP2IR discovery helpers."""

from unittest.mock import AsyncMock, MagicMock

from pyitach import ItachDiscoveryBeacon
import pytest

from homeassistant.components.itachip2ir.const import DOMAIN
from homeassistant.components.itachip2ir.discovery import (
    FLOW_THROTTLE_SECONDS,
    ItachDiscovery,
    async_discover_once,
    async_wait_for_device_id,
)
from homeassistant.config_entries import SOURCE_DISCOVERY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.1.211"
OTHER_HOST = "192.168.1.212"
NEW_HOST = "192.168.1.250"
UNIQUE_ID = "GlobalCache_000C1E123456"


async def test_async_discover_once_returns_none_when_no_beacon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HA wrapper returns None when hardware discovery finds no beacon."""

    async def fake_discover_once(timeout: float) -> None:
        return None

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery._async_discover_once",
        fake_discover_once,
    )

    assert await async_discover_once(timeout=1.0) is None


async def test_async_discover_once_filters_non_ip2ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HA wrapper filters non-IP2IR Global Caché beacons."""

    async def fake_discover_once(timeout: float) -> ItachDiscoveryBeacon:
        return ItachDiscoveryBeacon(
            host=HOST,
            uuid=UNIQUE_ID,
            model="iTachIP2SL",
        )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery._async_discover_once",
        fake_discover_once,
    )

    assert await async_discover_once(timeout=1.0) is None


async def test_async_discover_once_returns_ip2ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HA wrapper returns discovered IP2IR data."""

    async def fake_discover_once(timeout: float) -> ItachDiscoveryBeacon:
        return ItachDiscoveryBeacon(
            host=HOST,
            uuid=UNIQUE_ID,
            model="iTachIP2IR",
        )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery._async_discover_once",
        fake_discover_once,
    )

    assert await async_discover_once(timeout=1.0) == {
        "host": HOST,
        "uuid": UNIQUE_ID,
        "model": "iTachIP2IR",
    }


async def test_async_wait_for_device_id_returns_matching_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for a matching host returns the discovered UUID."""

    async def fake_discover_once(timeout: float) -> dict[str, str]:
        return {
            "host": HOST,
            "uuid": UNIQUE_ID,
            "model": "iTachIP2IR",
        }

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST, timeout=10.0) == UNIQUE_ID


async def test_async_wait_for_device_id_returns_none_for_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for device ID returns None when discovery finds nothing."""

    async def fake_discover_once(timeout: float) -> None:
        return None

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST) is None


async def test_async_wait_for_device_id_returns_none_for_host_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for device ID ignores beacons from another host."""

    async def fake_discover_once(timeout: float) -> dict[str, str]:
        return {
            "host": OTHER_HOST,
            "uuid": UNIQUE_ID,
            "model": "iTachIP2IR",
        }

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        fake_discover_once,
    )

    assert await async_wait_for_device_id(HOST) is None


async def test_async_wait_for_device_id_returns_none_for_blank_host() -> None:
    """Test waiting for a blank host returns None without discovery."""
    assert await async_wait_for_device_id("   ") is None


async def test_async_wait_for_device_id_uses_discovery_cache(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test waiting for device ID uses the discovery cache first."""
    discovery = ItachDiscovery(hass)
    discovery._known_devices[HOST] = UNIQUE_ID
    discover_once = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.async_discover_once",
        discover_once,
    )

    assert (
        await async_wait_for_device_id(HOST, timeout=10.0, discovery=discovery)
        == UNIQUE_ID
    )
    discover_once.assert_not_awaited()


def test_known_device_id_lookup(hass: HomeAssistant) -> None:
    """Test known device ID lookup."""
    discovery = ItachDiscovery(hass)

    assert discovery.get_known_device_id(HOST) is None

    discovery._known_devices[HOST] = UNIQUE_ID

    assert discovery.get_known_device_id(HOST) == UNIQUE_ID


def test_known_device_id_blank_host_returns_none(hass: HomeAssistant) -> None:
    """Test known device lookup handles blank host."""
    discovery = ItachDiscovery(hass)

    assert discovery.get_known_device_id("   ") is None


def test_is_already_configured_false(hass: HomeAssistant) -> None:
    """Test _is_already_configured returns false when entry is unknown."""
    discovery = ItachDiscovery(hass)

    assert not discovery._is_already_configured(UNIQUE_ID)


def test_is_already_configured_true(hass: HomeAssistant) -> None:
    """Test _is_already_configured returns true for configured unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title="iTach IP2IR",
    )
    entry.add_to_hass(hass)

    discovery = ItachDiscovery(hass)

    assert discovery._is_already_configured(UNIQUE_ID)


def test_configured_entry_invalid_unique_id_returns_none(hass: HomeAssistant) -> None:
    """Test configured entry lookup rejects invalid unique IDs."""
    discovery = ItachDiscovery(hass)

    assert discovery._configured_entry("not-a-valid-id") is None


def test_configured_device_host_update(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery updates host for an already configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="iTach IP2IR (192.168.1.100)",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    assert entry.data["port"] == 4998
    assert entry.title == f"iTach IP2IR ({HOST})"
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_configured_device_host_update_preserves_custom_title(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery host update preserves user/custom entry title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="Living Room iTach",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    assert entry.title == "Living Room iTach"
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_configured_device_host_update_skips_options_override(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery does not update host when options override host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        options={"host": "192.168.1.250"},
        title="iTach IP2IR",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == "192.168.1.100"
    schedule_reload.assert_not_called()


def test_configured_device_host_update_skips_unchanged_host(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery skips update when host has not changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)

    assert entry.data["host"] == HOST
    schedule_reload.assert_not_called()


def test_configured_device_host_update_requires_same_host_confirmation(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test host update confirmation resets when discovered host changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": "192.168.1.100", "port": 4998},
        title="iTach IP2IR (192.168.1.100)",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, HOST)
    discovery._update_configured_host(entry, OTHER_HOST)

    assert entry.data["host"] == "192.168.1.100"
    schedule_reload.assert_not_called()

    discovery._update_configured_host(entry, OTHER_HOST)

    assert entry.data["host"] == OTHER_HOST
    schedule_reload.assert_called_once_with(entry.entry_id)


def test_configured_device_host_update_blank_host_noops(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery host update ignores blank discovered host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )
    entry.add_to_hass(hass)

    schedule_reload = MagicMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        schedule_reload,
    )

    discovery = ItachDiscovery(hass)
    discovery._update_configured_host(entry, "   ")

    assert entry.data["host"] == HOST
    schedule_reload.assert_not_called()


def test_flow_throttle(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
) -> None:
    """Test discovery flow throttling."""
    discovery = ItachDiscovery(hass)

    now = 1000.0
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.time.monotonic",
        lambda: now,
    )

    assert not discovery._is_flow_throttled(UNIQUE_ID)

    discovery._mark_flow_started(UNIQUE_ID)

    assert discovery._is_flow_throttled(UNIQUE_ID)


def test_flow_throttle_expires(
    monkeypatch: pytest.MonkeyPatch,
    hass: HomeAssistant,
) -> None:
    """Test expired discovery flow throttle entries are pruned."""
    discovery = ItachDiscovery(hass)

    current_time = 1000.0

    def fake_monotonic() -> float:
        return current_time

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.time.monotonic",
        fake_monotonic,
    )

    discovery._mark_flow_started(UNIQUE_ID)
    assert discovery._is_flow_throttled(UNIQUE_ID)

    current_time = 1000.0 + FLOW_THROTTLE_SECONDS + 1

    assert not discovery._is_flow_throttled(UNIQUE_ID)
    assert UNIQUE_ID not in discovery._recent_flows


async def test_async_start_listener_failure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery start handles listener start failure."""
    listener = MagicMock()
    listener.async_start = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.ItachDiscoveryListener",
        MagicMock(return_value=listener),
    )

    discovery = ItachDiscovery(hass)
    await discovery.async_start()

    assert discovery._listener is None


async def test_async_start_success_and_idempotent(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery start creates one listener and is idempotent."""
    listener = MagicMock()
    listener.async_start = AsyncMock(return_value=True)

    listener_factory = MagicMock(return_value=listener)
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.discovery.ItachDiscoveryListener",
        listener_factory,
    )

    discovery = ItachDiscovery(hass)

    await discovery.async_start()
    await discovery.async_start()

    assert discovery._listener is listener
    listener_factory.assert_called_once()
    listener.async_start.assert_awaited_once()


async def test_async_stop_cleanup(hass: HomeAssistant) -> None:
    """Test discovery stop stops listener and clears caches."""
    listener = MagicMock()
    listener.async_stop = AsyncMock()
    discovery = ItachDiscovery(hass)
    discovery._listener = listener
    discovery._known_devices[HOST] = UNIQUE_ID
    discovery._recent_flows[UNIQUE_ID] = 1000.0
    discovery._pending_host_updates["entry-id"] = {"host": HOST, "count": 1}

    await discovery.async_stop()

    assert discovery._listener is None
    assert discovery._known_devices == {}
    assert discovery._recent_flows == {}
    assert discovery._pending_host_updates == {}
    listener.async_stop.assert_awaited_once()


async def test_handle_beacon_triggers_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handler starts a discovery flow for a valid beacon."""
    hass = MagicMock()
    async_init = AsyncMock(return_value={"type": "form"})
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    monkeypatch.setattr(
        hass.config_entries,
        "async_entries",
        MagicMock(return_value=[]),
    )

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    assert discovery.get_known_device_id(HOST) == UNIQUE_ID
    async_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={
            "host": HOST,
            "port": 4998,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )


async def test_handle_beacon_ignores_missing_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handler ignores beacons missing UUID."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid="not-a-device-id", model="iTachIP2IR")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_ignores_non_ip2ir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handler ignores non-IP2IR Global Caché devices."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2SL")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_ignores_already_configured_and_updates_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handler updates host and skips flow for configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": 4998},
        title=f"iTach IP2IR ({HOST})",
    )

    hass = MagicMock()
    async_init = AsyncMock()
    update_entry = MagicMock()
    schedule_reload = MagicMock()

    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    monkeypatch.setattr(
        hass.config_entries,
        "async_entries",
        MagicMock(return_value=[entry]),
    )
    monkeypatch.setattr(hass.config_entries, "async_update_entry", update_entry)
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", schedule_reload)

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=NEW_HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )
    update_entry.assert_not_called()
    schedule_reload.assert_not_called()

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=NEW_HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_not_awaited()
    update_entry.assert_called_once_with(
        entry,
        title=f"iTach IP2IR ({NEW_HOST})",
        data={
            "host": NEW_HOST,
            "port": 4998,
        },
    )
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_handle_beacon_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handler skips recently started discovery flows."""
    hass = MagicMock()
    async_init = AsyncMock()
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    monkeypatch.setattr(
        hass.config_entries,
        "async_entries",
        MagicMock(return_value=[]),
    )

    discovery = ItachDiscovery(hass)
    monkeypatch.setattr(discovery, "_is_flow_throttled", lambda unique_id: True)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_not_awaited()


async def test_handle_beacon_flow_start_exception_is_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handler handles discovery flow startup exceptions."""
    hass = MagicMock()
    async_init = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(hass.config_entries.flow, "async_init", async_init)
    monkeypatch.setattr(
        hass.config_entries,
        "async_entries",
        MagicMock(return_value=[]),
    )

    discovery = ItachDiscovery(hass)

    await discovery._async_handle_beacon(
        ItachDiscoveryBeacon(host=HOST, uuid=UNIQUE_ID, model="iTachIP2IR")
    )

    async_init.assert_awaited_once()
