"""Tests for iZone discovery service."""

from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.izone import discovery as izone_discovery
from homeassistant.components.izone.const import DATA_DISCOVERY_SERVICE, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .conftest import (
    async_load_yaml_exclude,
    create_mock_controller,
    create_mock_discovery_service,
)

from tests.common import MockConfigEntry


async def test_async_start_discovery_service_stops_on_home_assistant_stop(
    hass: HomeAssistant,
    mock_pizone_discovery_service: Mock,
) -> None:
    """Test discovery service is stopped on Home Assistant shutdown."""
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.discovery",
            return_value=mock_pizone_discovery_service,
        ),
    ):
        await izone_discovery.async_start_discovery_service(hass)

        assert DATA_DISCOVERY_SERVICE in hass.data

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_pizone_discovery_service.start_discovery.assert_awaited_once()
    mock_pizone_discovery_service.close.assert_awaited_once()
    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_async_maybe_stop_keeps_running_when_actionable_flow_exists(
    hass: HomeAssistant,
) -> None:
    """Discovery should stay running while an actionable iZone flow is in progress."""
    service = create_mock_discovery_service()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with (
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_handler",
            return_value=[{"context": {"source": config_entries.SOURCE_USER}}],
        ),
        patch(
            "homeassistant.components.izone.discovery.async_stop_discovery_service",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_not_awaited()
    service.async_schedule_idle_stop.assert_called_once()


async def test_async_maybe_stop_keeps_running_when_actionable_entry_exists(
    hass: HomeAssistant,
) -> None:
    """Discovery should stay running while an enabled, non-ignored entry exists."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        data={},
    ).add_to_hass(hass)

    service = create_mock_discovery_service()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with patch(
        "homeassistant.components.izone.discovery.async_stop_discovery_service",
        new=AsyncMock(),
    ) as mock_stop:
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_not_awaited()
    service.async_schedule_idle_stop.assert_called_once()


async def test_async_maybe_stop_stops_when_only_disabled_entry_matches_controller(
    hass: HomeAssistant,
) -> None:
    """Discovery should stop when only disabled/ignored controllers remain."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        disabled_by=config_entries.ConfigEntryDisabler.USER,
        data={},
    ).add_to_hass(hass)

    service = create_mock_discovery_service(create_mock_controller("000000001"))
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with patch(
        "homeassistant.components.izone.discovery.async_stop_discovery_service",
        new=AsyncMock(),
    ) as mock_stop:
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_awaited_once_with(hass)
    service.async_schedule_idle_stop.assert_not_called()


async def test_async_discover_controllers_starts_shared_service_when_missing(
    hass: HomeAssistant,
) -> None:
    """Starting discovery without refresh does not trigger extra wait/rescan work."""
    controller = create_mock_controller(device_ip="192.0.2.3")
    service = create_mock_discovery_service(controller)

    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        return_value=service,
    ) as mock_start:
        controllers = await izone_discovery.async_discover_controllers(hass)

    assert list(controllers) == ["000000001"]
    mock_start.assert_awaited_once()
    service.pi_disco.fetch_controller.assert_not_awaited()
    service.pi_disco.fetch_controllers.assert_awaited_once_with()


async def test_async_discover_controllers_refresh_after_start_calls_fetch_controllers(
    hass: HomeAssistant,
) -> None:
    """Refresh after starting discovery delegates to fetch_controllers with timeout."""
    controller = create_mock_controller(device_ip="192.0.2.3")
    service = create_mock_discovery_service(controller)

    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        return_value=service,
    ) as mock_start:
        controllers = await izone_discovery.async_discover_controllers(
            hass, refresh=True
        )

    assert list(controllers) == ["000000001"]
    mock_start.assert_awaited_once()
    service.pi_disco.fetch_controllers.assert_awaited_once_with(timeout=ANY)


async def test_async_discover_controllers_refresh_calls_fetch_controllers(
    hass: HomeAssistant,
) -> None:
    """Refresh without UID delegates to fetch_controllers with timeout."""
    service = create_mock_discovery_service()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    controllers = await izone_discovery.async_discover_controllers(hass, refresh=True)

    assert controllers == {}
    service.pi_disco.fetch_controllers.assert_awaited_once_with(timeout=ANY)


async def test_async_discover_controllers_waits_for_requested_uid(
    hass: HomeAssistant,
) -> None:
    """Refresh with wait_for_uid calls fetch_controller and returns all controllers."""
    service = create_mock_discovery_service()
    hass.data[DATA_DISCOVERY_SERVICE] = service
    requested = create_mock_controller("000000777", "192.0.2.77")

    async def _fetch_and_add(uid: str, timeout: float | None = None) -> None:
        service.pi_disco.controllers[uid] = requested

    service.pi_disco.fetch_controller.side_effect = _fetch_and_add

    controllers = await izone_discovery.async_discover_controllers(
        hass,
        refresh=True,
        wait_for_uid="000000777",
    )

    assert controllers == {requested.device_uid: requested}
    service.pi_disco.fetch_controller.assert_awaited_once_with("000000777", timeout=ANY)


async def test_async_discover_controllers_returns_empty_when_start_fails(
    hass: HomeAssistant,
) -> None:
    """Startup errors while creating discovery are propagated to the caller."""
    with (
        patch(
            "homeassistant.components.izone.discovery.async_start_discovery_service",
            side_effect=OSError,
        ),
        pytest.raises(OSError),
    ):
        await izone_discovery.async_discover_controllers(hass, refresh=True)


def test_controller_discovered_dispatches_signal_and_reschedules_idle_stop(
    hass: HomeAssistant,
) -> None:
    """Discovered controller should dispatch signal and cancel prior idle-stop handle."""
    service = izone_discovery.DiscoveryService(hass)
    previous_handle = Mock()
    new_handle = Mock()
    service._idle_stop_handle = previous_handle
    controller = create_mock_controller("000000001", "192.0.2.1")

    with (
        patch.object(hass.loop, "call_later", return_value=new_handle),
        patch(
            "homeassistant.components.izone.discovery.async_dispatcher_send"
        ) as mock_send,
    ):
        service.controller_discovered(controller)

    previous_handle.cancel.assert_called_once()
    assert service._idle_stop_handle is new_handle
    mock_send.assert_called_once_with(
        hass,
        izone_discovery.DISPATCH_CONTROLLER_DISCOVERED,
        controller,
    )


async def test_is_ignored_or_excluded_uid_returns_true_for_yaml_exclude(
    hass: HomeAssistant,
) -> None:
    """UIDs listed in YAML exclude are treated as ignored/excluded."""
    await async_load_yaml_exclude(hass, "000000009")

    assert izone_discovery._async_is_ignored_or_excluded_uid(hass, "000000009") is True


async def test_async_maybe_stop_returns_when_service_not_started(
    hass: HomeAssistant,
) -> None:
    """No-op when maybe-stop is called without a discovery service instance."""
    await izone_discovery.async_maybe_stop_discovery_service(hass)


async def test_async_start_discovery_service_returns_existing_instance(
    hass: HomeAssistant,
) -> None:
    """Starting discovery returns existing service when already running."""
    existing = Mock()
    hass.data[DATA_DISCOVERY_SERVICE] = existing

    disco = await izone_discovery.async_start_discovery_service(hass)

    assert disco is existing


async def test_async_maybe_stop_stops_when_no_controllers_remain(
    hass: HomeAssistant,
) -> None:
    """Discovery stops when no controllers are tracked and nothing is actionable."""
    service = create_mock_discovery_service()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with (
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_handler",
            return_value=[],
        ),
        patch(
            "homeassistant.components.izone.discovery.async_stop_discovery_service",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_awaited_once_with(hass)


async def test_async_maybe_stop_keeps_running_when_controller_not_ignored(
    hass: HomeAssistant,
) -> None:
    """Discovery remains active if at least one discovered controller is still actionable."""
    service = create_mock_discovery_service(create_mock_controller("000000001"))
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with (
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_handler",
            return_value=[],
        ),
        patch(
            "homeassistant.components.izone.discovery.async_stop_discovery_service",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_not_awaited()
    service.async_schedule_idle_stop.assert_called_once()


async def test_async_stop_discovery_service_returns_when_not_started(
    hass: HomeAssistant,
) -> None:
    """Stop is a no-op if discovery service was never started."""
    await izone_discovery.async_stop_discovery_service(hass)


async def test_async_stop_discovery_service_clears_stop_listener(
    hass: HomeAssistant,
) -> None:
    """Stop should remove the stop listener when it exists."""
    service = Mock()
    stop_listener = Mock()
    service.remove_stop_listener = stop_listener
    service.remove_config_flow_listener = None
    service.async_cancel_idle_stop = Mock()
    service.pi_disco.close = AsyncMock()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    await izone_discovery.async_stop_discovery_service(hass)

    stop_listener.assert_called_once()
    assert service.remove_stop_listener is None
