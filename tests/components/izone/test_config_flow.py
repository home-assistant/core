"""Tests for iZone config flow."""

import asyncio
from collections.abc import Generator
import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import izone as izone_component
from homeassistant.components.izone import config_flow
from homeassistant.components.izone.const import IZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _make_controller(uid: str = "000000001", ip: str = "192.0.2.1") -> Mock:
    """Return a minimal Mock iZone controller with uid and ip set."""
    controller = Mock()
    controller.device_uid = uid
    controller.device_ip = ip
    return controller


def _setup_shared_discovery(hass: HomeAssistant, *controllers: Mock) -> Mock:
    """Install a mock shared discovery service in hass.data and return it."""
    service = Mock()
    service.pi_disco.controllers = {c.device_uid: c for c in controllers}
    service.pi_disco.add_listener = Mock()
    service.pi_disco.remove_listener = Mock()
    hass.data["izone_discovery"] = service
    return service


@contextlib.contextmanager
def _mock_temporary_discovery(
    *controllers: Mock, resolve_host: str | None = None
) -> Generator[Mock]:
    """Patch pizone.discovery to deliver *controllers* to the listener then close."""
    listener_holder: dict[str, config_flow._ControllerDiscoveryListener] = {}

    def _deliver_all() -> None:
        for c in controllers:
            listener_holder["listener"].controller_discovered(c)

    discovery = Mock()
    discovery.start_discovery = AsyncMock(side_effect=_deliver_all)
    discovery.close = AsyncMock()

    def _factory(
        created: config_flow._ControllerDiscoveryListener, session: object
    ) -> Mock:
        listener_holder["listener"] = created
        return discovery

    patches: list = [
        patch(
            "homeassistant.components.izone.config_flow.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.config_flow.pizone.discovery",
            side_effect=_factory,
        ),
    ]
    if resolve_host is not None:
        patches.insert(
            0,
            patch(
                "homeassistant.components.izone.config_flow._async_resolve_host",
                return_value=resolve_host,
            ),
        )

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield discovery


@pytest.fixture
def mock_entry_setup() -> Generator[None]:
    """Patch climate platform setup and discovery-service start for entry-creating tests."""
    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Config flow – user source (broadcast discovery + manual host)
# ---------------------------------------------------------------------------


async def test_found(hass: HomeAssistant, mock_entry_setup: None) -> None:
    """Test finding iZone controller via broadcast discovery."""
    controller = _make_controller(ip="192.0.2.1")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {"host": "192.0.2.1"}


async def test_manual_host_success(hass: HomeAssistant, mock_entry_setup: None) -> None:
    """Test successful manual host validation."""
    with patch(
        "homeassistant.components.izone.config_flow._async_get_controller_uid",
        return_value="000000001",
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone.local"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {"host": "izone.local"}


async def test_multiple_entries_allowed(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test multiple iZone controllers can be configured."""
    with patch(
        "homeassistant.components.izone.config_flow._async_get_controller_uid",
        side_effect=["000000001", "000000002"],
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone-1.local"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "iZone 000000001"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone-2.local"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {"host": "izone-2.local"}


async def test_reuses_existing_discovery_service(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test config flow reuses the running discovery service without starting a new one."""
    controller = _make_controller("000000002", "192.0.2.2")
    _setup_shared_discovery(hass, controller)

    with patch(
        "homeassistant.components.izone.config_flow.pizone.discovery",
    ) as mock_pizone_discovery:
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {"host": "192.0.2.2"}
    mock_pizone_discovery.assert_not_called()


async def test_manual_host_uses_shared_discovery_service(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test manual host entry resolves UID from the shared discovery service."""
    controller = _make_controller("000000002", "192.0.2.2")
    _setup_shared_discovery(hass, controller)

    with patch(
        "homeassistant.components.izone.config_flow.pizone.discovery",
    ) as mock_pizone_discovery:
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.2"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {"host": "192.0.2.2"}
    mock_pizone_discovery.assert_not_called()


# ---------------------------------------------------------------------------
# Config flow – import source
# ---------------------------------------------------------------------------


async def test_import_discovers_and_creates_entry(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test YAML import discovers a controller and creates an entry."""
    controller = _make_controller(ip="192.0.2.1")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {"host": "192.0.2.1"}


# ---------------------------------------------------------------------------
# Config flow – HomeKit source
# ---------------------------------------------------------------------------


async def test_homekit_confirm_uses_discovered_host(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test HomeKit flow confirms and uses the discovered controller IP, not the HomeKit host."""
    controller = _make_controller(ip="192.0.2.3")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": "203.0.113.1",
                "properties": {"md": "iZone 000000001"},
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["title_placeholders"] == {"name": "iZone 000000001"}
        assert result["description_placeholders"] == {
            "controller_uid": "000000001",
            "host": "192.0.2.3",
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {"host": "192.0.2.3"}


async def test_homekit_uses_homekit_host_when_uid_matches(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test HomeKit keeps the HomeKit host when it validates to the same controller UID."""
    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={},
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_get_controller_uid",
            return_value="000000001",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": "192.0.2.3",
                "properties": {"md": "iZone 000000001"},
            },
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "192.0.2.3"}


async def test_homekit_confirm_falls_back_to_discovery_when_host_not_resolved(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test confirm creates entry from a re-discovered controller when the HomeKit host doesn't resolve."""
    controller = _make_controller(ip="192.0.2.3")

    with (
        patch(
            "homeassistant.components.izone.config_flow._async_get_controller_uid",
            return_value=None,
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            side_effect=[{}, {controller.device_uid: controller}],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": "203.0.113.1",
                "properties": {"md": "iZone 000000001"},
            },
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "192.0.2.3"}


# ---------------------------------------------------------------------------
# Error / edge-case paths
# ---------------------------------------------------------------------------


async def test_not_found(hass: HomeAssistant) -> None:
    """Test abort when no device is found during broadcast discovery."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()


async def test_manual_host_failed_validation(hass: HomeAssistant) -> None:
    """Test failed manual host validation shows cannot_connect."""
    with patch(
        "homeassistant.components.izone.config_flow._async_get_controller_uid",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "bad-host"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_homekit_without_model_falls_back_to_confirm_unknowns(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow with a non-iZone model string shows unknown UID on confirm."""
    result = await hass.config_entries.flow.async_init(
        IZONE,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"host": "192.0.2.3", "properties": {"md": "Other Device"}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "controller_uid": "unknown",
        "host": "192.0.2.3",
    }


async def test_homekit_confirm_aborts_when_nothing_found(hass: HomeAssistant) -> None:
    """Test HomeKit confirm aborts when no host or controllers can be resolved."""
    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={},
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_get_controller_uid",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": "203.0.113.1",
                "properties": {"md": "iZone 000000001"},
            },
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# ---------------------------------------------------------------------------
# Lifecycle / setup integration
# ---------------------------------------------------------------------------


async def test_async_setup_starts_import_flow(hass: HomeAssistant) -> None:
    """Test YAML config triggers an import flow."""
    with (
        patch.object(hass.config_entries.flow, "async_init") as mock_async_init,
        patch.object(
            hass,
            "async_create_task",
            side_effect=lambda target: target.close(),
        ) as mock_create_task,
    ):
        assert await izone_component.async_setup(hass, {IZONE: {"exclude": []}})

    mock_async_init.assert_called_once_with(
        IZONE, context={"source": config_entries.SOURCE_IMPORT}
    )
    mock_create_task.assert_called_once()


async def test_async_setup_entry_stops_discovery_on_forward_failure(
    hass: HomeAssistant,
) -> None:
    """Test discovery service is stopped when platform forward setup fails."""
    entry = MockConfigEntry(domain=IZONE, data={"host": "192.0.2.1"})

    with (
        pytest.raises(RuntimeError, match="boom"),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ) as mock_start,
        patch(
            "homeassistant.components.izone.async_stop_discovery_service",
            return_value=None,
        ) as mock_stop,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=RuntimeError("boom"),
        ),
    ):
        await izone_component.async_setup_entry(hass, entry)

    mock_start.assert_awaited_once()
    mock_stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# Helper / internals unit tests
# ---------------------------------------------------------------------------


async def test_controller_discovery_listener_sets_event_for_target_ip() -> None:
    """Test listener accumulates controllers and only sets ready for the target IP."""
    ready = asyncio.Event()
    listener = config_flow._ControllerDiscoveryListener(ready, "192.0.2.3")

    other = _make_controller("other", "192.0.2.4")
    listener.controller_discovered(other)
    assert listener.controllers == {"other": other}
    assert not ready.is_set()

    matching = _make_controller("match", "192.0.2.3")
    listener.controller_discovered(matching)
    assert listener.controllers == {"other": other, "match": matching}
    assert ready.is_set()


async def test_async_discover_controllers_uses_temporary_service(
    hass: HomeAssistant,
) -> None:
    """Test temporary discovery service path returns all discovered controllers."""
    controller = _make_controller(ip="192.0.2.3")

    with _mock_temporary_discovery(controller) as discovery:
        controllers = await config_flow._async_discover_controllers(hass)

    assert list(controllers) == ["000000001"]
    discovery.start_discovery.assert_awaited_once()
    discovery.close.assert_awaited_once()


async def test_async_discover_controllers_uses_temporary_service_with_target_ip(
    hass: HomeAssistant,
) -> None:
    """Test temporary discovery service filters results to the resolved target IP."""
    nonmatching = _make_controller("000000003", "192.0.2.4")
    matching = _make_controller(ip="192.0.2.3")

    with _mock_temporary_discovery(
        nonmatching, matching, resolve_host="192.0.2.3"
    ) as discovery:
        controllers = await config_flow._async_discover_controllers(hass, "izone.local")

    assert list(controllers) == ["000000001"]
    assert controllers["000000001"].device_ip == "192.0.2.3"
    discovery.start_discovery.assert_awaited_once()
    discovery.close.assert_awaited_once()


async def test_async_discover_controllers_reuses_shared_service_and_rescans(
    hass: HomeAssistant,
) -> None:
    """Test shared discovery service rescan path returns a newly discovered controller."""
    service = _setup_shared_discovery(hass)  # start with no controllers

    async def rescan_side_effect() -> None:
        listener = service.pi_disco.add_listener.call_args.args[0]
        listener.controller_discovered(_make_controller(ip="192.0.2.3"))

    service.pi_disco.rescan = AsyncMock(side_effect=rescan_side_effect)

    with patch(
        "homeassistant.components.izone.config_flow._async_resolve_host",
        return_value="192.0.2.3",
    ):
        controllers = await config_flow._async_discover_controllers(hass, "izone.local")

    assert list(controllers) == ["000000001"]
    service.pi_disco.rescan.assert_awaited_once()
    service.pi_disco.add_listener.assert_called_once()
    service.pi_disco.remove_listener.assert_called_once()


async def test_async_discover_controllers_returns_empty_for_unresolvable_host(
    hass: HomeAssistant,
) -> None:
    """Test discovery returns an empty dict when the target hostname cannot be resolved."""
    with patch(
        "homeassistant.components.izone.config_flow._async_resolve_host",
        return_value=None,
    ):
        assert await config_flow._async_discover_controllers(hass, "bad-host") == {}


async def test_async_resolve_host_failures() -> None:
    """Test host resolution returns None on OS error or empty address list."""
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(side_effect=OSError)
        assert await config_flow._async_resolve_host("bad-host") is None

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[])
        assert await config_flow._async_resolve_host("empty-host") is None


async def test_async_get_controller_uid_returns_none_when_no_controller(
    hass: HomeAssistant,
) -> None:
    """Test UID lookup returns None when discovery finds no matching controller."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        assert await config_flow._async_get_controller_uid(hass, "izone.local") is None
