"""Tests for iZone config entry setup and unload."""

from asyncio import CancelledError
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pizone import (
    ControllerCommandError,
    ControllerEndpoint,
    DeviceReconfigurationError,
    EndpointVerifyError,
    UnpairedBridgeError,
    VerifyFailure,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.izone.const import DOMAIN
from homeassistant.components.izone.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import create_mock_controller, create_mock_zone

EXCLUDE_ISSUE_ID = "yaml_exclude_unused"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Entry loads climate entities and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_discovery_service.create_controller.assert_awaited_once()
    mock_controller.refresh_all.assert_awaited()
    assert hass.states.get("climate.izone_controller_000000001") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_controller.close.assert_awaited()
    mock_discovery_service.close.assert_awaited()


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_setup_removes_stale_zone_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Zone devices the controller no longer reports are removed on setup."""
    mock_config_entry.add_to_hass(hass)
    controller_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "000000001")},
    )
    live_zone_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "000000001", 0)},  # type: ignore[arg-type]
        via_device_id=controller_device.id,
    )
    stale_zone_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "000000001", 5)},  # type: ignore[arg-type]
        via_device_id=controller_device.id,
    )

    with patch.object(
        device_registry,
        "async_remove_device",
        wraps=device_registry.async_remove_device,
    ) as remove_device:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    remove_device.assert_called_once_with(stale_zone_device.id)
    assert device_registry.async_get(stale_zone_device.id) is None
    assert device_registry.async_get(controller_device.id) is not None
    assert device_registry.async_get(live_zone_device.id) is not None


@pytest.mark.usefixtures("mock_create_discovery")
async def test_reconfigured_system_reloads_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_discovery_service: Mock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """A poll that finds the system reprogrammed reloads with the new zones."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.bedroom") is None

    mock_controller.refresh_all.side_effect = DeviceReconfigurationError(
        {"NoOfZones": (1, 2)}
    )
    reprogrammed = create_mock_controller(zones_total=2)
    reprogrammed.zones = [*mock_zones, create_mock_zone(index=1, name="Bedroom")]
    mock_discovery_service.create_controller.return_value = reprogrammed
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_controller.close.assert_awaited()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    for entity_id in ("climate.izone_controller_000000001", "climate.bedroom"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "000000001", 1),  # type: ignore[arg-type]
        mock_config_entry.entry_id,
    )


async def test_migrate_heals_legacy_domain_unique_id(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Migrate binds unique_id=DOMAIN to the sole discovered endpoint and loads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[ControllerEndpoint(uid="000000001", host="192.0.2.1")]
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.unique_id == "000000001"
    assert entry.data[CONF_HOST] == "192.0.2.1"
    assert entry.title == "iZone 000000001"
    mock_discovery_service.create_controller.assert_awaited_once()


async def test_migrate_heals_legacy_domain_unique_id_keeps_custom_title(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Legacy rebind keeps a user-customised title instead of rewriting it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Living Room AC",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[ControllerEndpoint(uid="000000001", host="192.0.2.1")]
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert entry.title == "Living Room AC"


async def _async_setup_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


def _discovery_flow_uids(hass: HomeAssistant) -> set[str]:
    return {
        flow["context"]["unique_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    }


def _legacy_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )


@pytest.mark.usefixtures("mock_create_discovery")
@pytest.mark.parametrize(
    ("config", "issue_expected"),
    [
        pytest.param({DOMAIN: {CONF_EXCLUDE: ["000000002"]}}, True, id="exclude"),
        pytest.param({DOMAIN: {CONF_EXCLUDE: []}}, False, id="empty_exclude"),
        pytest.param({DOMAIN: {}}, False, id="no_exclude"),
        pytest.param({}, False, id="no_yaml"),
    ],
)
async def test_yaml_exclude_raises_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: ConfigType,
    issue_expected: bool,
) -> None:
    """A non-empty YAML exclude raises a repair saying it has no effect."""
    await _async_setup_yaml(hass, config)

    assert (
        issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID) is not None
    ) is issue_expected


@pytest.mark.usefixtures("mock_create_discovery")
async def test_setup_removes_ignored_legacy_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An ignored legacy entry is removed and does not hold back the repair."""
    ignored = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        source=SOURCE_IGNORE,
        data={},
        version=2,
    )
    ignored.add_to_hass(hass)
    kept = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000009",
        source=SOURCE_IGNORE,
        data={},
    )
    kept.add_to_hass(hass)

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: ["000000002"]}})

    assert hass.config_entries.async_get_entry(ignored.entry_id) is None
    assert hass.config_entries.async_get_entry(kept.entry_id) is kept
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID)


@pytest.mark.usefixtures("mock_create_discovery")
async def test_disabled_legacy_entry_holds_exclude_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A disabled legacy entry has not migrated yet, so the repair waits."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        version=2,
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: ["000000002"]}})

    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
@pytest.mark.parametrize(
    "exclude",
    [
        pytest.param(["000000002"], id="list"),
        pytest.param("000000002", id="scalar"),
    ],
)
async def test_migrate_legacy_domain_unique_id_filters_yaml_excluded(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_service: Mock,
    exclude: str | list[str],
) -> None:
    """YAML exclude picks the controller and shelves the rest, then raises the repair."""
    entry = _legacy_entry()
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[
            ControllerEndpoint(uid="000000001", host="192.0.2.1"),
            ControllerEndpoint(uid="000000002", host="192.0.2.2"),
        ]
    )

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: exclude}})

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert entry.data[CONF_HOST] == "192.0.2.1"
    assert _discovery_flow_uids(hass) == {"000000002"}
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID)


@pytest.mark.usefixtures("mock_create_discovery")
async def test_migrate_legacy_domain_unique_id_only_excluded_retries(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_service: Mock,
) -> None:
    """An excluded controller is never the legacy entry's controller, so it retries."""
    entry = _legacy_entry()
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[ControllerEndpoint(uid="000000002", host="192.0.2.2")]
    )

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: ["000000002"]}})

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.unique_id == DOMAIN
    assert _discovery_flow_uids(hass) == {"000000002"}
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_create_discovery")
async def test_migrate_legacy_domain_unique_id_multiple_after_exclude_fails(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_service: Mock,
) -> None:
    """Several controllers left after exclude fail migration and hold the repair."""
    entry = _legacy_entry()
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[
            ControllerEndpoint(uid="000000001", host="192.0.2.1"),
            ControllerEndpoint(uid="000000002", host="192.0.2.2"),
            ControllerEndpoint(uid="000000003", host="192.0.2.3"),
        ]
    )

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: ["000000002"]}})

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.unique_id == DOMAIN
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_migrate_legacy_domain_unique_id_retry_defers_exclude_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_service: Mock,
) -> None:
    """The repair waits until a retried legacy migration succeeds."""
    entry = _legacy_entry()
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(return_value=[])

    await _async_setup_yaml(hass, {DOMAIN: {CONF_EXCLUDE: ["000000002"]}})

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID) is None

    mock_discovery_service.discover_all.return_value = [
        ControllerEndpoint(uid="000000001", host="192.0.2.1"),
        ControllerEndpoint(uid="000000002", host="192.0.2.2"),
    ]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert issue_registry.async_get_issue(DOMAIN, EXCLUDE_ISSUE_ID)


async def test_migrate_legacy_domain_unique_id_filters_already_configured(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Already-configured UIDs are skipped when binding a legacy DOMAIN entry."""
    configured = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={CONF_HOST: "192.0.2.2"},
        version=2,
        minor_version=2,
    )
    configured.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[
            ControllerEndpoint(uid="000000001", host="192.0.2.1"),
            ControllerEndpoint(uid="000000002", host="192.0.2.2"),
        ]
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert entry.data[CONF_HOST] == "192.0.2.1"


async def test_migrate_v1_legacy_domain_unique_id(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """v1 migrate discovers and writes UID + CONF_HOST (no blank-data step)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={"host": "203.0.113.1"},
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[ControllerEndpoint(uid="000000001", host="192.0.2.1")]
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert entry.data == {CONF_HOST: "192.0.2.1"}
    assert entry.title == "iZone 000000001"


async def test_migrate_complete_v2_1_bumps_minor_without_discovery(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Complete v2.1 entry (real UID + host) only bumps minor_version; no discover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.unique_id == "000000001"
    assert entry.data == {CONF_HOST: "192.0.2.1"}
    mock_discovery_service.discover_all.assert_not_called()
    mock_discovery_service.discover_by_uid.assert_not_called()
    mock_discovery_service.create_controller.assert_awaited_once()


async def test_migrate_legacy_domain_unique_id_no_eligible_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Legacy unique_id=DOMAIN with no eligible endpoint leaves SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(return_value=[])

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.unique_id == DOMAIN
    assert entry.data == {}


async def test_migrate_legacy_domain_unique_id_multiple_eligible_fails(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Legacy unique_id=DOMAIN with multiple eligible endpoints is MIGRATION_ERROR."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_all = AsyncMock(
        return_value=[
            ControllerEndpoint(uid="000000001", host="192.0.2.1"),
            ControllerEndpoint(uid="000000002", host="192.0.2.2"),
        ]
    )

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 2
    assert entry.minor_version == 1


async def test_migrate_heals_missing_host_via_discover_endpoint(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Real UID with empty data recovers CONF_HOST via discover_by_uid in migrate."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_by_uid = AsyncMock(
        return_value=ControllerEndpoint(uid="000000001", host="192.0.2.1")
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data[CONF_HOST] == "192.0.2.1"
    mock_discovery_service.create_controller.assert_awaited_once()


async def test_migrate_missing_host_not_found_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Real UID with empty data and no discovered endpoint leaves SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_by_uid = AsyncMock(return_value=None)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.minor_version == 1
    assert entry.error_reason_translation_key == "controller_not_found"
    assert entry.error_reason_translation_placeholders == {"uid": "000000001"}
    mock_discovery_service.create_controller.assert_not_awaited()


async def test_migrate_missing_host_verify_error_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """A UID whose address fails the HTTP check leaves SETUP_RETRY with its host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_by_uid = AsyncMock(
        side_effect=EndpointVerifyError(
            "192.0.2.1", VerifyFailure.NO_REPLY, uid="000000001"
        )
    )

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "cannot_connect"
    assert entry.error_reason_translation_placeholders == {"host": "192.0.2.1"}
    mock_discovery_service.create_controller.assert_not_awaited()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(OSError("bind failed"), id="oserror"),
        pytest.param(RuntimeError("discovery already exists"), id="runtimeerror"),
    ],
)
async def test_migrate_legacy_domain_unique_id_discovery_error_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    side_effect: Exception,
) -> None:
    """Discovery startup errors for legacy DOMAIN unique_id leave SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.async_discover_all_endpoints",
        new=AsyncMock(side_effect=side_effect),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.minor_version == 1
    assert entry.error_reason_translation_key == "discovery_failed_legacy"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(OSError("bind failed"), id="oserror"),
        pytest.param(RuntimeError("discovery already exists"), id="runtimeerror"),
    ],
)
async def test_migrate_missing_host_discover_error_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    side_effect: Exception,
) -> None:
    """Discovery startup errors while resolving host leave SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.async_discover_endpoint",
        new=AsyncMock(side_effect=side_effect),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.minor_version == 1
    assert entry.error_reason_translation_key == "discovery_failed_host"


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "translation_key", "placeholders"),
    [
        pytest.param(
            ConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            {"host": "192.0.2.1"},
            id="connection-error",
        ),
        pytest.param(
            UnpairedBridgeError("unpaired"),
            ConfigEntryState.SETUP_ERROR,
            "bridge_unpaired",
            None,
            id="unpaired-bridge",
        ),
        pytest.param(
            ControllerCommandError("rejected"),
            ConfigEntryState.SETUP_ERROR,
            "setup_rejected",
            {"host": "192.0.2.1"},
            id="command-rejected",
        ),
    ],
)
async def test_setup_create_controller_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """create_controller failures map to retry vs error entry states."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery_service.create_controller = AsyncMock(side_effect=side_effect)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == placeholders


async def test_setup_discovery_bind_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """UDP bind failure during discovery start leaves the entry in SETUP_RETRY."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(side_effect=OSError("bind failed")),
        ),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "discovery_start_failed"


@pytest.mark.parametrize(
    ("side_effect", "connected"),
    [
        pytest.param(ConnectionError("gone"), True, id="connection-error"),
        pytest.param(ControllerCommandError("rejected"), True, id="command-rejected"),
        pytest.param(None, False, id="system-offline"),
        pytest.param(
            DeviceReconfigurationError({"NoOfZones": (1, 2)}),
            True,
            id="system-reconfigured",
        ),
    ],
)
async def test_setup_first_refresh_failure_closes_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    side_effect: Exception | None,
    connected: bool,
) -> None:
    """A failed first refresh closes the controller and retries setup.

    This includes a reachable bridge whose iZone system is offline, and a system
    reprogrammed mid-setup, which must leave the retry backoff to setup.
    """
    mock_config_entry.add_to_hass(hass)
    mock_controller.refresh_all = AsyncMock(side_effect=side_effect)
    mock_controller.connected = connected

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_controller.close.assert_awaited()
    mock_schedule_reload.assert_not_called()


async def test_setup_platform_failure_closes_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
) -> None:
    """A failure during platform forward still releases the controller claim."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError("platform boom"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_controller.close.assert_awaited()


async def test_setup_cancelled_closes_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
) -> None:
    """Cancellation after create_controller still closes it to release the UID claim."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.IZoneCoordinator.async_config_entry_first_refresh",
        side_effect=CancelledError,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_controller.close.assert_awaited()


async def test_address_changed_updates_config_entry_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Library address-change callback persists the new host on the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_address_changed = mock_discovery_service.create_controller.await_args.kwargs[
        "on_address_changed"
    ]
    on_address_changed(ControllerEndpoint(uid="000000001", host="192.0.2.99"))
    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_HOST] == "192.0.2.99"


async def test_address_changed_same_host_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Address callback with an unchanged host does not rewrite entry data."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    original = dict(mock_config_entry.data)
    on_address_changed = mock_discovery_service.create_controller.await_args.kwargs[
        "on_address_changed"
    ]
    on_address_changed(ControllerEndpoint(uid="000000001", host="192.0.2.1"))
    await hass.async_block_till_done()

    assert dict(mock_config_entry.data) == original


async def test_last_unload_stops_shared_discovery(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Unloading the last loaded entry closes the shared discovery service."""
    first = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
        entry_id="entry_1",
        version=2,
        minor_version=2,
    )
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={CONF_HOST: "192.0.2.2"},
        entry_id="entry_2",
        version=2,
        minor_version=2,
    )
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    async def _create_controller(uid: str, host: str, **kwargs: object) -> Mock:
        if uid == "000000001":
            return first_controller
        return second_controller

    mock_discovery_service.create_controller = AsyncMock(side_effect=_create_controller)

    first.add_to_hass(hass)
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert first.state is ConfigEntryState.LOADED

    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert second.state is ConfigEntryState.LOADED

    mock_discovery_service.close.reset_mock()
    assert await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()
    mock_discovery_service.close.assert_not_awaited()

    assert await hass.config_entries.async_unload(second.entry_id)
    await hass.async_block_till_done()
    mock_discovery_service.close.assert_awaited_once()


async def test_setup_after_last_unload_recreates_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """After the last unload stops discovery, a later setup starts it again."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_create_discovery.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_discovery_service.close.assert_awaited_once()

    mock_create_discovery.reset_mock()
    mock_discovery_service.close.reset_mock()
    mock_controller.close.reset_mock()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_create_discovery.assert_awaited_once()
    mock_discovery_service.create_controller.assert_awaited()
