"""Test the Zinvolt initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from zinvolt.exceptions import ZinvoltAuthenticationError, ZinvoltError

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Zinvolt device."""
    await setup_integration(hass, mock_config_entry)
    devices = device_registry._devices
    for device in devices.values():
        assert device == snapshot(name=list(device.identifiers)[0][1])


async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
) -> None:
    """Test that a unit sub-device links to its main battery device via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    battery_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ZVG011025120088"), mock_config_entry.entry_id
    )
    assert battery_device is not None

    unit_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "BAT002"), mock_config_entry.entry_id
    )
    assert unit_device is not None
    assert unit_device.via_device_id == battery_device.id


@pytest.mark.parametrize(
    "method", ["get_batteries", "get_units", "get_battery_status", "get_battery_unit"]
)
async def test_setup_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    method: str,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    getattr(mock_zinvolt_client, method).side_effect = ZinvoltAuthenticationError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    "method", ["get_batteries", "get_units", "get_battery_status", "get_battery_unit"]
)
async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    method: str,
) -> None:
    """Test a connection error during setup retries the setup."""
    getattr(mock_zinvolt_client, method).side_effect = ZinvoltError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "update_failed"


@pytest.mark.parametrize("method", ["get_battery_status", "get_battery_unit"])
async def test_update_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test an authentication error during a scheduled update starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    getattr(mock_zinvolt_client, method).side_effect = ZinvoltAuthenticationError
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
