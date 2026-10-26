"""Tests for Mitsubishi Comfort Cloud setup and isolation."""

from unittest.mock import AsyncMock, patch

from mitsubishi_comfort import CloudIndoorUnit, DeviceInfo
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mitsubishi_comfort_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import MOCK_SERIAL, MOCK_SITE

from tests.components.mitsubishi_comfort.conftest import create_mock_indoor_unit


async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Set up cloud entities without LAN discovery or address repairs."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(
        mock_config_entry.runtime_data[MOCK_SERIAL].device, CloudIndoorUnit
    )
    assert (
        entity_registry.async_get_entity_id("climate", DOMAIN, MOCK_SERIAL)
        == "climate.living_room"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert not device.connections
    assert not issue_registry.issues
    assert hass.states.get("climate.living_room") == snapshot
    mock_cloud_account.get_zone_state.assert_awaited_once_with(MOCK_SITE, MOCK_SERIAL)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "state", "reauth_steps"),
    [
        pytest.param(
            AuthenticationError("expired"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
            id="auth",
        ),
        pytest.param(
            DeviceConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            [],
            id="connection",
        ),
    ],
)
@pytest.mark.parametrize("method", ["login", "get_zones", "get_device_details"])
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    error: Exception,
    state: ConfigEntryState,
    reauth_steps: list[str],
    method: str,
) -> None:
    """Setup failures retry or start reauthentication as appropriate."""
    getattr(mock_cloud_account, method).side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is state
    assert [
        flow["step_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ] == reauth_steps


async def test_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """An account without supported units fails setup."""
    mock_cloud_account.get_zones.return_value = []
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_offline_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """An offline unit causes setup to retry."""
    mock_cloud_account.get_device_details.return_value = {"connected": False}
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("error", "reauth_steps"),
    [
        pytest.param(DeviceConnectionError("offline"), [], id="connection"),
        pytest.param(AuthenticationError("expired"), ["reauth_confirm"], id="auth"),
    ],
)
async def test_partial_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    error: Exception,
    reauth_steps: list[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One failed unit does not hide working units on the account."""
    mock_cloud_account.get_zones.return_value.append(
        {"name": "Bedroom", "adapter": {"deviceSerial": "SECOND"}}
    )
    mock_cloud_account.get_device_details.side_effect = [
        mock_cloud_account.get_device_details.return_value,
        error,
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room").state == "cool"
    assert hass.states.get("climate.bedroom").state == STATE_UNAVAILABLE
    assert [
        flow["step_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ] == reauth_steps
    assert caplog.text.count("Error fetching initial data for Bedroom:") == 1
    mock_cloud_account.get_device_details.side_effect = error
    await mock_config_entry.runtime_data["SECOND"].async_refresh()
    assert caplog.text.count("Error fetching initial data for Bedroom:") == 1
    assert "Error fetching mitsubishi_comfort_cloud_SECOND data" not in caplog.text
    assert "Authentication failed while fetching" not in caplog.text
    mock_cloud_account.get_device_details.side_effect = None
    await mock_config_entry.runtime_data["SECOND"].async_refresh()
    assert hass.states.get("climate.bedroom").state == "cool"


async def test_unexpected_refresh_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unexpected first-refresh errors are not swallowed by partial setup."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.mitsubishi_comfort_cloud.coordinator.MitsubishiComfortCloudCoordinator.async_config_entry_first_refresh",
        side_effect=RuntimeError("unexpected"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_discovery_filters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Skip sites without IDs, stations, and zones without adapters."""
    mock_cloud_account.get_sites.return_value.insert(0, {})
    mock_cloud_account.get_zones.return_value.extend(
        [
            {
                "name": "Station",
                "adapter": {"deviceSerial": "STATION", "isHeadless": True},
            },
            {"name": "Empty zone"},
        ]
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert list(mock_config_entry.runtime_data) == [MOCK_SERIAL]
    mock_cloud_account.get_zones.assert_awaited_once_with(MOCK_SITE)


async def test_local_data_does_not_switch_transport(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Cloud control remains selected even when local data becomes available."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = entity_registry.async_get("climate.living_room")
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "addresses": {"aa:bb:cc:dd:ee:ff": "192.168.1.100"},
            "credentials": {
                MOCK_SERIAL: {
                    "password": "local",
                    "crypto_serial": "local",
                    "mac": "aa:bb:cc:dd:ee:ff",
                }
            },
        },
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert isinstance(
        mock_config_entry.runtime_data[MOCK_SERIAL].device, CloudIndoorUnit
    )
    assert entity_registry.async_get("climate.living_room").id == before.id


async def test_cloud_reauth_leaves_local_entry_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Cloud authentication failures do not affect the same unit's local entry."""
    local_entry = MockConfigEntry(
        domain="mitsubishi_comfort",
        unique_id=mock_config_entry.unique_id,
        data={
            **mock_config_entry.data,
            "addresses": {"aa:bb:cc:dd:ee:ff": "192.168.1.100"},
        },
    )
    local_entry.add_to_hass(hass)
    local_device = create_mock_indoor_unit()
    local_account = AsyncMock()
    local_account.discover_devices.return_value = {
        MOCK_SERIAL: DeviceInfo(
            serial=MOCK_SERIAL,
            label="Living Room",
            address="",
            mac="aa:bb:cc:dd:ee:ff",
            unit_type="ductless",
            password="dGVzdA==",
            crypto_serial="0102030405060708090a",
        )
    }
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=local_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=local_device,
        ),
    ):
        assert await hass.config_entries.async_setup(local_entry.entry_id)
        await hass.async_block_till_done()
        local_entity = entity_registry.async_get("climate.living_room")
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        cloud_entity = entity_registry.async_get("climate.living_room_2")
        assert cloud_entity.device_id != local_entity.device_id
        assert cloud_entity.config_entry_id == mock_config_entry.entry_id
        assert local_entity.config_entry_id == local_entry.entry_id

        mock_cloud_account.get_device_details.side_effect = AuthenticationError(
            "expired"
        )
        await mock_config_entry.runtime_data[MOCK_SERIAL].async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("climate.living_room_2").state == STATE_UNAVAILABLE
        assert hass.states.get("climate.living_room").state == "cool"
        assert local_entry.state is ConfigEntryState.LOADED
        assert not hass.config_entries.flow.async_progress_by_handler(
            "mitsubishi_comfort"
        )
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert hass.states.get("climate.living_room").state == "cool"
        assert entity_registry.async_get("climate.living_room").id == local_entity.id
