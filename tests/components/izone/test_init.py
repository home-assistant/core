"""Tests for iZone config entry setup and unload."""

from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pizone import ControllerCommandError, ControllerEndpoint, UnpairedBridgeError
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.izone.const import DOMAIN
from homeassistant.components.izone.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import create_mock_controller

from tests.common import MockConfigEntry, async_fire_time_changed


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


async def test_setup_missing_host_fails(
    hass: HomeAssistant,
    mock_create_discovery: AsyncMock,
) -> None:
    """Hostless entries fail setup (unreleased WIP only)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


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


async def test_coordinator_refresh_failure_marks_climate_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_controller: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed coordinator refresh marks climate entities unavailable."""
    entity_id = "climate.izone_controller_000000001"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    mock_controller.refresh_all = AsyncMock(side_effect=ConnectionError("offline"))
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


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

@pytest.mark.usefixtures("init_integration")
async def test_climate_platform_loaded(hass: HomeAssistant) -> None:
    """Loaded entry exposes the climate domain."""
    assert hass.services.has_service(CLIMATE_DOMAIN, "set_temperature")
