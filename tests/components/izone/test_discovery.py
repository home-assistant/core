"""Tests for iZone discovery service lifecycle."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from pizone import ControllerEndpoint, DiscoveryService
import pytest

from homeassistant import config_entries
from homeassistant.components.izone import discovery as izone_discovery
from homeassistant.components.izone.const import DISCOVERY_SCAN_INTERVAL, DOMAIN
from homeassistant.components.izone.discovery import DATA_DISCOVERY_SERVICE
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .conftest import async_load_yaml_exclude, create_mock_endpoint

from tests.common import MockConfigEntry, async_fire_time_changed


def _mock_pizone_service() -> Mock:
    """Return a mock pizone DiscoveryService."""
    service = Mock(spec=DiscoveryService)
    service.scan = AsyncMock()
    service.close = AsyncMock()
    service.discover_all = AsyncMock(return_value=[])
    service.discover_by_uid = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_pizone_create_discovery() -> Generator[tuple[AsyncMock, Mock]]:
    """Patch create_discovery and yield (mock_create, mock_service)."""
    mock_service = _mock_pizone_service()
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(return_value=mock_service),
        ) as mock_create,
    ):
        yield mock_create, mock_service


async def test_ensure_discovery_starts_and_stops_on_homeassistant_stop(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Ensure starts discovery with an initial scan and closes on HA stop."""
    mock_create, mock_service = mock_pizone_create_discovery

    service = await izone_discovery.async_ensure_discovery(hass)

    assert service is mock_service
    mock_create.assert_awaited_once()
    mock_service.scan.assert_awaited_once()

    # Second ensure reuses the same service.
    assert await izone_discovery.async_ensure_discovery(hass) is mock_service
    mock_create.assert_awaited_once()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_service.close.assert_awaited_once()


async def test_ensure_discovery_recreates_after_stop(
    hass: HomeAssistant,
) -> None:
    """After a clean stop, ensure starts a fresh create_discovery."""
    first_service = _mock_pizone_service()
    second_service = _mock_pizone_service()

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=[first_service, second_service]),
        ) as mock_create,
    ):
        assert await izone_discovery.async_ensure_discovery(hass) is first_service
        await izone_discovery.async_stop_discovery(hass)
        first_service.close.assert_awaited_once()
        assert DATA_DISCOVERY_SERVICE not in hass.data

        assert await izone_discovery.async_ensure_discovery(hass) is second_service

    assert mock_create.await_count == 2
    assert isinstance(
        hass.data[DATA_DISCOVERY_SERVICE], izone_discovery.DiscoveryRuntime
    )


async def test_ensure_discovery_serializes_concurrent_reopen(
    hass: HomeAssistant,
) -> None:
    """Concurrent ensure after stop still shares a single reopen create."""
    first_service = _mock_pizone_service()
    second_service = _mock_pizone_service()
    started = asyncio.Event()
    release = asyncio.Event()
    create_calls = 0

    async def _create(**_kwargs: object) -> Mock:
        nonlocal create_calls
        create_calls += 1
        if create_calls == 1:
            return first_service
        started.set()
        await release.wait()
        return second_service

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=_create),
        ) as mock_create,
    ):
        assert await izone_discovery.async_ensure_discovery(hass) is first_service
        await izone_discovery.async_stop_discovery(hass)

        task_one = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await started.wait()
        task_two = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await asyncio.sleep(0)
        assert create_calls == 2
        assert isinstance(hass.data[DATA_DISCOVERY_SERVICE], asyncio.Future)

        release.set()
        service_one, service_two = await asyncio.gather(task_one, task_two)

    assert service_one is second_service
    assert service_two is second_service
    assert mock_create.await_count == 2


async def test_ensure_discovery_serializes_concurrent_create(
    hass: HomeAssistant,
) -> None:
    """Concurrent ensure callers share one create_discovery and the same service."""
    mock_service = _mock_pizone_service()
    started = asyncio.Event()
    release = asyncio.Event()
    create_calls = 0

    async def _slow_create(**_kwargs: object) -> Mock:
        nonlocal create_calls
        create_calls += 1
        started.set()
        await release.wait()
        return mock_service

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=_slow_create),
        ) as mock_create,
    ):
        task_one = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await started.wait()
        task_two = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await asyncio.sleep(0)
        assert create_calls == 1
        assert isinstance(hass.data[DATA_DISCOVERY_SERVICE], asyncio.Future)

        release.set()
        service_one, service_two = await asyncio.gather(task_one, task_two)

    assert service_one is mock_service
    assert service_two is mock_service
    mock_create.assert_awaited_once()
    assert isinstance(
        hass.data[DATA_DISCOVERY_SERVICE], izone_discovery.DiscoveryRuntime
    )


async def test_ensure_discovery_failure_fails_concurrent_waiters(
    hass: HomeAssistant,
) -> None:
    """Create failure clears the slot and fails every concurrent waiter."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _failing_create(**_kwargs: object) -> Mock:
        started.set()
        await release.wait()
        raise OSError("bind failed")

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=_failing_create),
        ),
    ):
        task_one = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await started.wait()
        task_two = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(task_one, task_two, return_exceptions=True)

    assert all(isinstance(result, OSError) for result in results)
    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_stop_discovery_aborts_in_flight_create(
    hass: HomeAssistant,
) -> None:
    """Stopping while create is pending fails the Future and clears the slot."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_create(**_kwargs: object) -> Mock:
        started.set()
        await release.wait()
        return _mock_pizone_service()

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=_slow_create),
        ),
    ):
        ensure_task = hass.async_create_task(
            izone_discovery.async_ensure_discovery(hass), eager_start=True
        )
        await started.wait()
        await izone_discovery.async_stop_discovery(hass)
        release.set()
        with pytest.raises(RuntimeError, match="stopped before start completed"):
            await ensure_task

    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_slow_scan_fires_while_entry_loaded(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Shared timer keeps hunting for new devices while an entry is loaded."""
    _, mock_service = mock_pizone_create_discovery
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        data={CONF_HOST: "192.0.2.1"},
        version=2,
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, config_entries.ConfigEntryState.LOADED)

    await izone_discovery.async_ensure_discovery(hass)
    mock_service.scan.reset_mock()

    async_fire_time_changed(
        hass, utcnow() + DISCOVERY_SCAN_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    mock_service.scan.assert_awaited_once()


async def test_endpoint_discovered_starts_config_flow(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Discovered endpoints surface as integration discovery flows."""
    mock_create, _mock_service = mock_pizone_create_discovery

    await izone_discovery.async_ensure_discovery(hass)
    on_endpoint_discovered = mock_create.await_args.kwargs["on_endpoint_discovered"]
    on_endpoint_discovered(ControllerEndpoint(uid="000000001", host="192.0.2.1"))
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(progress) == 1
    assert progress[0]["context"]["unique_id"] == "000000001"
    assert progress[0]["step_id"] == "confirm"


async def test_endpoint_discovered_skips_yaml_excluded(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """YAML exclude suppresses integration discovery for that UID."""
    await async_load_yaml_exclude(hass, "000000009")
    mock_create, _mock_service = mock_pizone_create_discovery

    with patch("homeassistant.helpers.discovery_flow.async_create_flow") as mock_flow:
        await izone_discovery.async_ensure_discovery(hass)
        mock_create.await_args.kwargs["on_endpoint_discovered"](
            ControllerEndpoint(uid="000000009", host="192.0.2.9")
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_flow.assert_not_called()


async def test_maybe_stop_keeps_discovery_for_loaded_entry(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Idle stop does not tear down discovery while a loaded entry remains."""
    _, mock_service = mock_pizone_create_discovery
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        data={CONF_HOST: "192.0.2.1"},
        version=2,
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, config_entries.ConfigEntryState.LOADED)

    await izone_discovery.async_ensure_discovery(hass)
    mock_service.close.reset_mock()
    await izone_discovery.async_maybe_stop_discovery(hass)

    mock_service.close.assert_not_awaited()


async def test_maybe_stop_keeps_discovery_for_actionable_flow(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Idle stop keeps discovery while a user config flow is in progress."""
    _, mock_service = mock_pizone_create_discovery
    await izone_discovery.async_ensure_discovery(hass)
    mock_service.close.reset_mock()

    with patch.object(
        hass.config_entries.flow,
        "async_progress_by_handler",
        return_value=[{"context": {"source": config_entries.SOURCE_USER}}],
    ):
        await izone_discovery.async_maybe_stop_discovery(hass)

    mock_service.close.assert_not_awaited()


@pytest.mark.parametrize(
    ("entry_state", "expect_close"),
    [
        pytest.param(
            config_entries.ConfigEntryState.SETUP_RETRY,
            False,
            id="setup_retry",
        ),
        pytest.param(
            config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
            False,
            id="setup_in_progress",
        ),
        pytest.param(
            config_entries.ConfigEntryState.SETUP_ERROR,
            True,
            id="setup_error",
        ),
        pytest.param(
            config_entries.ConfigEntryState.NOT_LOADED,
            True,
            id="not_loaded",
        ),
    ],
)
async def test_maybe_stop_respects_entry_setup_state(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
    entry_state: config_entries.ConfigEntryState,
    expect_close: bool,
) -> None:
    """Keep discovery for in-flight/retry setup; stop for error or unloaded."""
    _, mock_service = mock_pizone_create_discovery
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        data={CONF_HOST: "192.0.2.1"},
        version=2,
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, entry_state)

    await izone_discovery.async_ensure_discovery(hass)
    mock_service.close.reset_mock()
    await izone_discovery.async_maybe_stop_discovery(hass)

    assert mock_service.close.await_count == int(expect_close)


async def test_maybe_stop_closes_when_idle(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Idle stop closes discovery when nothing actionable remains."""
    _, mock_service = mock_pizone_create_discovery
    await izone_discovery.async_ensure_discovery(hass)
    mock_service.close.reset_mock()

    await izone_discovery.async_maybe_stop_discovery(hass)

    mock_service.close.assert_awaited_once()


async def test_stop_discovery_is_noop_when_not_started(hass: HomeAssistant) -> None:
    """Stop is a no-op if discovery was never started."""
    await izone_discovery.async_stop_discovery(hass)


async def test_ensure_discovery_propagates_oserror(hass: HomeAssistant) -> None:
    """Bind failures from create_discovery propagate to the caller."""
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=OSError("bind failed")),
        ),
        pytest.raises(OSError, match="bind failed"),
    ):
        await izone_discovery.async_ensure_discovery(hass)

    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_setup_runtime_error_from_discovery_retries(
    hass: HomeAssistant,
) -> None:
    """Process-global discovery conflicts surface as SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
        version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=RuntimeError("already running")),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_discover_all_endpoints(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """User/HomeKit scan returns endpoints from discover_all."""
    _, mock_service = mock_pizone_create_discovery
    endpoint = create_mock_endpoint("000000001", "192.0.2.1")
    mock_service.discover_all = AsyncMock(return_value=[endpoint])

    result = await izone_discovery.async_discover_all_endpoints(hass)

    assert result == {endpoint.uid: endpoint}
    mock_service.discover_all.assert_awaited_once()


async def test_discover_endpoint_by_uid(
    hass: HomeAssistant,
    mock_pizone_create_discovery: tuple[AsyncMock, Mock],
) -> None:
    """Targeted lookup returns a single endpoint from discover_by_uid."""
    _, mock_service = mock_pizone_create_discovery
    endpoint = create_mock_endpoint("000000001", "192.0.2.1")
    mock_service.discover_by_uid = AsyncMock(return_value=endpoint)

    result = await izone_discovery.async_discover_endpoint(hass, "000000001")

    assert result == endpoint
    mock_service.discover_by_uid.assert_awaited_once_with("000000001")
