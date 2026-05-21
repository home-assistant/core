"""Tests for the Kii Audio coordinator."""

import asyncio
from unittest.mock import AsyncMock, call

from aiokii import KiiAudioError

from homeassistant.components.kii_audio.coordinator import KiiAudioCoordinator


def _coordinator() -> KiiAudioCoordinator:
    """Return a minimal coordinator instance for callback tests."""
    coordinator = KiiAudioCoordinator.__new__(KiiAudioCoordinator)
    coordinator._ready = asyncio.Event()
    return coordinator


def test_connection_loss_before_ready_does_not_mark_unavailable() -> None:
    """Test early connection loss is handled by setup timeout instead."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]

    coordinator._handle_connection_state(False)

    assert errors == []


def test_connection_loss_after_ready_marks_coordinator_unavailable() -> None:
    """Test connection loss after setup marks coordinator unavailable."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]
    coordinator._ready.set()

    coordinator._handle_connection_state(False)

    assert len(errors) == 1
    assert isinstance(errors[0], KiiAudioError)
    assert str(errors[0]) == "WebSocket disconnected"


def test_connection_available_does_not_mark_update_error() -> None:
    """Test connected callbacks do not mark update errors."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]
    coordinator._ready.set()

    coordinator._handle_connection_state(True)

    assert errors == []


def test_connection_available_after_error_marks_coordinator_available() -> None:
    """Test connected callbacks clear an existing update error."""
    coordinator = _coordinator()
    coordinator.data = {"systemName": "Kii System", "zones": []}
    coordinator.last_update_success = False
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_connection_state(True)

    assert updates == [{"systemName": "Kii System", "zones": []}]


async def test_coordinator_client_methods_delegate_to_client() -> None:
    """Test coordinator client wrappers delegate to the aiokii client."""
    coordinator = _coordinator()
    coordinator.client = AsyncMock()

    await coordinator.async_start()
    await coordinator.async_stop()
    await coordinator.async_set_zone_setting("zone-id", "setting.path", "value")
    await coordinator.async_set_zone_volume("zone-id", -42.0)
    await coordinator.async_set_zone_mute("zone-id", True)
    await coordinator.async_set_zone_power("zone-id", False)
    await coordinator.async_set_zone_source("zone-id", "digital_auto")

    coordinator.client.start.assert_awaited_once_with()
    coordinator.client.stop.assert_awaited_once_with()
    assert coordinator.client.set_zone_setting.await_args_list == [
        call("zone-id", "setting.path", "value"),
        call("zone-id", "audio.volume", -42.0),
        call("zone-id", "audio.mute", True),
        call("zone-id", "power", False),
        call("zone-id", "audio.source", "digital_auto"),
    ]


def test_handle_system_info_event_sets_data_and_ready() -> None:
    """Test system info events update coordinator data."""
    coordinator = _coordinator()
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_event("pushSystemInfo", {"systemName": "Kii System"})

    assert updates == [{"systemName": "Kii System"}]
    assert coordinator._ready.is_set()


def test_handle_zone_setting_event_updates_cached_data() -> None:
    """Test zone setting events update nested cached data."""
    coordinator = _coordinator()
    coordinator.data = {
        "zones": [
            {
                "zoneId": "zone-id",
                "settings": {"audio": {"volume": -50.0}},
            }
        ]
    }
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_event(
        "pushZoneSetting",
        {
            "zoneId": "zone-id",
            "setting": "audio.volume",
            "value": -40.0,
            "updateCount": 5,
        },
    )

    assert updates == [
        {
            "zones": [
                {
                    "zoneId": "zone-id",
                    "settings": {
                        "audio": {"volume": -40.0},
                        "updateCount": 5,
                    },
                }
            ]
        }
    ]
    assert coordinator.data == {
        "zones": [
            {
                "zoneId": "zone-id",
                "settings": {"audio": {"volume": -50.0}},
            }
        ]
    }


def test_handle_zone_setting_ignores_invalid_payloads() -> None:
    """Test invalid zone setting payloads do not update data."""
    coordinator = _coordinator()
    coordinator.data = {"zones": []}
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_zone_setting({"zoneId": 1, "setting": "audio.volume"})
    coordinator._handle_zone_setting({"zoneId": "zone-id", "setting": 1})
    coordinator.data = {"zones": {}}
    coordinator._handle_zone_setting(
        {"zoneId": "zone-id", "setting": "audio.volume", "value": -40.0}
    )
    coordinator.data = {"zones": [{"zoneId": "zone-id", "settings": []}]}
    coordinator._handle_zone_setting(
        {"zoneId": "zone-id", "setting": "audio.volume", "value": -40.0}
    )

    assert updates == []


def test_handle_zone_setting_replaces_non_dict_path() -> None:
    """Test zone setting events replace non-dict intermediate path values."""
    coordinator = _coordinator()
    coordinator.data = {
        "zones": [{"zoneId": "zone-id", "settings": {"audio": "invalid"}}]
    }
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_zone_setting(
        {"zoneId": "zone-id", "setting": "audio.volume", "value": -40.0}
    )

    assert updates == [
        {"zones": [{"zoneId": "zone-id", "settings": {"audio": {"volume": -40.0}}}]}
    ]


async def test_wait_ready_returns_after_system_info_event() -> None:
    """Test waiting for readiness returns once ready is set."""
    coordinator = _coordinator()
    coordinator._ready.set()

    await coordinator.async_wait_ready()


def test_handle_zone_setting_ignores_unknown_zone() -> None:
    """Test zone setting payloads for unknown zones do not update data."""
    coordinator = _coordinator()
    coordinator.data = {"zones": [{"zoneId": "other-zone", "settings": {}}]}
    updates: list[dict[str, object]] = []
    coordinator.async_set_updated_data = updates.append  # type: ignore[method-assign]

    coordinator._handle_zone_setting(
        {"zoneId": "zone-id", "setting": "audio.volume", "value": -40.0}
    )

    assert updates == []
