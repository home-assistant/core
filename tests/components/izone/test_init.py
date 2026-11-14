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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import create_mock_controller, create_mock_zone

EXCLUDE_ISSUE_ID = "yaml_exclude_unused"
LEGACY_ISSUE_ID = "legacy_entry_removed"


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
async def test_setup_removes_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices that aren't this controller or its current zones are removed on setup.

    That includes zones the controller no longer reports, and another
    controller's device left behind by an old legacy rebind.
    """
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
    foreign_controller_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "000000002")},
    )
    foreign_climate = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "000000002",
        config_entry=mock_config_entry,
        device_id=foreign_controller_device.id,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(stale_zone_device.id) is None
    assert device_registry.async_get(foreign_controller_device.id) is None
    assert entity_registry.async_get(foreign_climate.entity_id) is None
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


async def _async_setup_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


def _legacy_entry(
    version: int = 2,
    minor_version: int = 1,
    title: str = "iZone Aircon",
    data: dict[str, str] | None = None,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title=title,
        data=data or {},
        version=version,
        minor_version=minor_version,
        disabled_by=disabled_by,
    )


def _register_controller(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, uid: str
) -> dr.DeviceEntry:
    controller = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, uid)}
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, uid, 0)},  # type: ignore[arg-type]
        via_device_id=controller.id,
    )
    return controller


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
@pytest.mark.parametrize(
    ("legacy", "title"),
    [
        pytest.param(_legacy_entry(), "iZone 000000001", id="v2_1"),
        pytest.param(
            _legacy_entry(version=1, data={CONF_HOST: "203.0.113.1"}),
            "iZone 000000001",
            id="v1_stale_host",
        ),
        pytest.param(
            _legacy_entry(title="Living Room AC"), "Living Room AC", id="custom_title"
        ),
    ],
)
async def test_legacy_entry_bound_to_registered_controller(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_discovery_service: Mock,
    legacy: MockConfigEntry,
    title: str,
) -> None:
    """A legacy entry takes the UID its controller device was registered under.

    Its devices and entity IDs carry over unchanged.
    """
    legacy.add_to_hass(hass)
    controller_device = _register_controller(device_registry, legacy, "000000001")
    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "000000001", 0),  # type: ignore[arg-type]
        legacy.entry_id,
    )
    assert zone_device is not None
    climate = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "000000001",
        config_entry=legacy,
        device_id=controller_device.id,
        suggested_object_id="my_aircon",
    )

    await _async_setup_yaml(hass, {})

    assert legacy.state is ConfigEntryState.LOADED
    assert {
        device.id
        for device in dr.async_entries_for_config_entry(
            device_registry, legacy.entry_id
        )
    } == {controller_device.id, zone_device.id}
    assert hass.states.get(climate.entity_id) is not None
    assert legacy.unique_id == "000000001"
    assert legacy.title == title
    assert (legacy.version, legacy.minor_version) == (2, 2)
    assert legacy.data == {CONF_HOST: "192.0.2.1"}
    mock_discovery_service.discover_all.assert_not_called()
    mock_discovery_service.discover_by_uid.assert_awaited_once_with("000000001")


@pytest.mark.usefixtures("mock_create_discovery")
async def test_disabled_legacy_entry_bound_without_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_discovery_service: Mock,
) -> None:
    """A disabled legacy entry is bound too, and its controller can't be added again."""
    legacy = _legacy_entry(disabled_by=ConfigEntryDisabler.USER)
    legacy.add_to_hass(hass)
    _register_controller(device_registry, legacy, "000000001")

    await _async_setup_yaml(hass, {})

    assert legacy.state is ConfigEntryState.NOT_LOADED
    assert legacy.unique_id == "000000001"
    assert (legacy.version, legacy.minor_version) == (2, 2)
    assert legacy.data == {}
    mock_discovery_service.discover_by_uid.assert_not_called()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": "000000001",
        },
        data={CONF_HOST: "192.0.2.1"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_legacy_entry_bound_from_climate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Without a controller device, the controller climate entity gives the UID."""
    legacy = _legacy_entry()
    legacy.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "climate", DOMAIN, "000000001", config_entry=legacy
    )
    entity_registry.async_get_or_create(
        "climate", DOMAIN, "000000001_z1", config_entry=legacy
    )

    await _async_setup_yaml(hass, {})

    assert legacy.state is ConfigEntryState.LOADED
    assert legacy.unique_id == "000000001"


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="enabled"),
        pytest.param(ConfigEntryDisabler.USER, id="disabled"),
    ],
)
async def test_legacy_entry_bound_to_controller_not_yet_added(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    disabled_by: ConfigEntryDisabler | None,
) -> None:
    """Controllers that already have their own entry don't count for a legacy entry.

    Their leftover devices are removed from the legacy entry on setup.
    """
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={CONF_HOST: "192.0.2.2"},
        version=2,
        minor_version=2,
        disabled_by=disabled_by,
    ).add_to_hass(hass)
    legacy = _legacy_entry()
    legacy.add_to_hass(hass)
    _register_controller(device_registry, legacy, "000000001")
    _register_controller(device_registry, legacy, "000000002")

    await _async_setup_yaml(hass, {})

    assert legacy.state is ConfigEntryState.LOADED
    assert legacy.unique_id == "000000001"
    assert {
        identifier
        for device in dr.async_entries_for_config_entry(
            device_registry, legacy.entry_id
        )
        for identifier in device.identifiers
    } == {(DOMAIN, "000000001"), (DOMAIN, "000000001", 0)}


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_legacy_entry_replaces_ignore_of_its_controller(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """An Ignore of the legacy entry's own controller gives way to the legacy entry."""
    ignored = MockConfigEntry(
        domain=DOMAIN, unique_id="000000001", source=SOURCE_IGNORE, data={}
    )
    ignored.add_to_hass(hass)
    legacy = _legacy_entry()
    legacy.add_to_hass(hass)
    _register_controller(device_registry, legacy, "000000001")

    await _async_setup_yaml(hass, {})

    assert hass.config_entries.async_get_entry(ignored.entry_id) is None
    assert legacy.state is ConfigEntryState.LOADED
    assert legacy.unique_id == "000000001"


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
@pytest.mark.parametrize(
    "registered",
    [
        pytest.param([], id="never_had_controller"),
        pytest.param(["000000001"], id="controller_already_added"),
    ],
)
async def test_legacy_entry_without_controller_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    registered: list[str],
) -> None:
    """A legacy entry with no controller of its own is removed without a repair.

    The controller's own entry takes over the legacy entry's entities.
    """
    mock_config_entry.add_to_hass(hass)
    legacy = _legacy_entry(disabled_by=ConfigEntryDisabler.USER)
    legacy.add_to_hass(hass)
    entity_ids = [
        entity_registry.async_get_or_create(
            "climate",
            DOMAIN,
            uid,
            config_entry=legacy,
            device_id=_register_controller(device_registry, legacy, uid).id,
            suggested_object_id=f"legacy_{uid}",
        ).entity_id
        for uid in registered
    ]

    await _async_setup_yaml(hass, {})

    assert hass.config_entries.async_get_entry(legacy.entry_id) is None
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, LEGACY_ISSUE_ID) is None
    for entity_id in entity_ids:
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_legacy_entry_devices_take_precedence_over_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Climate entities are only used to find the UID when there are no devices."""
    mock_config_entry.add_to_hass(hass)
    legacy = _legacy_entry()
    legacy.add_to_hass(hass)
    _register_controller(device_registry, legacy, "000000001")
    entity_registry.async_get_or_create(
        "climate", DOMAIN, "000000002", config_entry=legacy
    )

    await _async_setup_yaml(hass, {})

    assert hass.config_entries.async_get_entry(legacy.entry_id) is None
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_legacy_entry_with_several_controllers_removed_with_repair(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Several registered controllers remove the entry and raise a repair.

    Setting up one of the listed controllers again clears the repair and
    restores its device's area and name and its entity's ID and name, as the
    repair promises.
    """
    legacy = _legacy_entry()
    legacy.add_to_hass(hass)
    _register_controller(device_registry, legacy, "000000002")
    controller_device = _register_controller(device_registry, legacy, "000000001")
    area = area_registry.async_create("Lounge")
    device_registry.async_update_device(
        controller_device.id, area_id=area.id, name_by_user="Main AC"
    )
    climate = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "000000001",
        config_entry=legacy,
        device_id=controller_device.id,
        suggested_object_id="my_aircon",
    )
    entity_registry.async_update_entity(climate.entity_id, name="My AC")

    await _async_setup_yaml(hass, {})

    assert hass.config_entries.async_get_entry(legacy.entry_id) is None
    issue = issue_registry.async_get_issue(DOMAIN, LEGACY_ISSUE_ID)
    assert issue is not None
    assert issue.is_persistent
    assert issue.translation_placeholders == {"uids": "000000001, 000000002"}

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, LEGACY_ISSUE_ID) is None
    device = device_registry.async_get(controller_device.id)
    assert device is not None
    assert device.config_entry_id == mock_config_entry.entry_id
    assert device.area_id == area.id
    assert device.name_by_user == "Main AC"
    entity = entity_registry.async_get(climate.entity_id)
    assert entity is not None
    assert entity.config_entry_id == mock_config_entry.entry_id
    assert entity.name == "My AC"


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
    """An ignored legacy entry is removed; other ignored entries are kept."""
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


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({CONF_HOST: "192.0.2.1"}, id="with_host"),
        pytest.param({}, id="without_host"),
    ],
)
async def test_migrate_v2_1_bumps_minor_without_discovery(
    hass: HomeAssistant,
    mock_discovery_service: Mock,
    data: dict[str, str],
) -> None:
    """Migration only bumps the version; a missing host is looked up by setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data=data,
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.data == {CONF_HOST: "192.0.2.1"}
    mock_discovery_service.discover_all.assert_not_called()
    mock_discovery_service.create_controller.assert_awaited_once()


@pytest.mark.usefixtures("mock_create_discovery", "mock_controller")
async def test_setup_without_host_finds_it_by_uid(
    hass: HomeAssistant,
    mock_discovery_service: Mock,
) -> None:
    """An entry without a host finds it by UID and stores it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_by_uid = AsyncMock(
        return_value=ControllerEndpoint(uid="000000001", host="192.0.2.7")
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == {CONF_HOST: "192.0.2.7"}
    mock_discovery_service.create_controller.assert_awaited_once()
    assert mock_discovery_service.create_controller.await_args.args == (
        "000000001",
        "192.0.2.7",
    )


@pytest.mark.usefixtures("mock_create_discovery")
@pytest.mark.parametrize(
    ("discover_by_uid", "translation_key", "placeholders"),
    [
        pytest.param(
            AsyncMock(return_value=None),
            "controller_not_found",
            {"uid": "000000001"},
            id="not_found",
        ),
        pytest.param(
            AsyncMock(
                side_effect=EndpointVerifyError(
                    "192.0.2.1", VerifyFailure.NO_REPLY, uid="000000001"
                )
            ),
            "cannot_connect",
            {"host": "192.0.2.1"},
            id="verify_error",
        ),
        pytest.param(
            AsyncMock(side_effect=OSError("bind failed")),
            "discovery_failed_host",
            None,
            id="oserror",
        ),
        pytest.param(
            AsyncMock(side_effect=RuntimeError("discovery already exists")),
            "discovery_failed_host",
            None,
            id="runtimeerror",
        ),
    ],
)
async def test_setup_without_host_lookup_failure_retries(
    hass: HomeAssistant,
    mock_discovery_service: Mock,
    discover_by_uid: AsyncMock,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """A failed host lookup leaves the entry retrying with no host stored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    mock_discovery_service.discover_by_uid = discover_by_uid

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == translation_key
    assert entry.error_reason_translation_placeholders == placeholders
    assert entry.data == {}
    mock_discovery_service.create_controller.assert_not_awaited()


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
