"""Tests for iZone config entry setup and unload."""

from asyncio import CancelledError
from unittest.mock import AsyncMock, Mock, patch

from pizone import ControllerCommandError, ControllerEndpoint, UnpairedBridgeError
import pytest

from homeassistant.components.izone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import async_load_yaml_exclude, create_mock_controller

from tests.common import MockConfigEntry


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


async def test_setup_heals_legacy_domain_unique_id(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Legacy unique_id=DOMAIN binds the sole discovered endpoint and loads."""
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
    assert entry.unique_id == "000000001"
    assert entry.data[CONF_HOST] == "192.0.2.1"
    assert entry.title == "iZone 000000001"
    mock_discovery_service.create_controller.assert_awaited_once()


async def test_setup_heals_legacy_domain_unique_id_keeps_custom_title(
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


async def test_setup_legacy_domain_unique_id_filters_yaml_excluded(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """YAML exclude narrows multiple discoveries to one eligible controller."""
    await async_load_yaml_exclude(hass, "000000002")
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


async def test_setup_legacy_domain_unique_id_filters_already_configured(
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


async def test_migrate_then_heals_legacy_domain_unique_id(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """v1 migrate clears data, then setup heal rebinds UID and CONF_HOST."""
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
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "000000001"
    assert entry.data == {CONF_HOST: "192.0.2.1"}
    assert entry.title == "iZone 000000001"


async def test_setup_legacy_domain_unique_id_no_eligible_retries(
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


async def test_setup_legacy_domain_unique_id_multiple_eligible_fails(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
) -> None:
    """Legacy unique_id=DOMAIN with multiple eligible endpoints is SETUP_ERROR."""
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
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_heals_missing_host_via_discover_endpoint(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    mock_controller: Mock,
) -> None:
    """Real UID with empty data recovers CONF_HOST via discover_by_uid."""
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
    assert entry.data[CONF_HOST] == "192.0.2.1"
    mock_discovery_service.create_controller.assert_awaited_once()


async def test_setup_missing_host_not_found_retries(
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
    mock_discovery_service.create_controller.assert_not_awaited()


async def test_setup_legacy_domain_unique_id_discovery_oserror_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
) -> None:
    """OSError while discovering for legacy DOMAIN unique_id leaves SETUP_RETRY."""
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
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_missing_host_discover_oserror_retries(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
) -> None:
    """OSError while resolving host for a real UID leaves SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.async_discover_endpoint",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (ConnectionError("offline"), ConfigEntryState.SETUP_RETRY),
        (UnpairedBridgeError("unpaired"), ConfigEntryState.SETUP_ERROR),
        (ControllerCommandError("rejected"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_create_controller_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_discovery_service: Mock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """create_controller failures map to retry vs error entry states."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery_service.create_controller = AsyncMock(side_effect=side_effect)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is expected_state


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


async def test_setup_first_refresh_failure_closes_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
) -> None:
    """A failed first refresh closes the controller and retries setup."""
    mock_config_entry.add_to_hass(hass)
    mock_controller.refresh_all = AsyncMock(side_effect=ConnectionError("gone"))

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_controller.close.assert_awaited()


async def test_setup_platform_failure_propagates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
) -> None:
    """A failure during platform forward leaves setup in error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError("platform boom"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_controller.close.assert_not_awaited()


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
    )
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={CONF_HOST: "192.0.2.2"},
        entry_id="entry_2",
        version=2,
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
