"""Test the Aqvify init."""

from datetime import timedelta
from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from pyaqvify import AqvifyAuthException, AqvifyDevices
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)

WATER_LEVEL_SENSOR = "sensor.device_1_level_from_top"
IN_FLOW_SENSOR = "sensor.device_1_inflow"
EXPECTED_WATER_LEVEL = "-0.136786005"
EXPECTED_IN_FLOW = "24.4735918930962"


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (None, ConfigEntryState.LOADED),
        (AqvifyAuthException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (ClientResponseError(Mock(), Mock(), status=500), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["no_error", "auth_error", "timeout_error", "communications_error"],
)
async def test_setup_entry_with_error(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with error."""
    mock_aqvify_client.async_get_account_id.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_device_registry_integration(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry integration creates correct devices."""
    await setup_integration(hass, mock_config_entry)

    # Get all devices created for this config entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    sorted_devices = sorted(
        device_entries, key=lambda dev_entry: dev_entry.serial_number
    )
    assert sorted_devices == snapshot


async def test_setup_entry_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with auth error triggers reauth flow."""
    mock_config_entry.add_to_hass(hass)

    mock_aqvify_client.async_get_account_id.side_effect = AqvifyAuthException(
        "Authentication failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_autoremove_stale_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stale devices are removed."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 2

    mock_aqvify_client.async_get_devices.return_value = AqvifyDevices(
        await async_load_json_array_fixture(hass, "removed_devices.json", DOMAIN)
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 1
    assert hass.states.get("sensor.device_2_level_from_top") is None


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that added devices are created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 2
    assert hass.states.get("sensor.device_3_level_from_top") is None

    mock_aqvify_client.async_get_devices.return_value = AqvifyDevices(
        await async_load_json_array_fixture(hass, "added_devices.json", DOMAIN)
    )

    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 3
    assert (
        hass.states.get("sensor.device_3_level_from_top").state == EXPECTED_WATER_LEVEL
    )


@pytest.mark.parametrize(
    ("exception", "log_message", "expected_state"),
    [
        (
            TimeoutError,
            "Timeout occurred while communicating",
            EXPECTED_WATER_LEVEL,
        ),
        (
            ClientResponseError(Mock(), Mock(), status=500),
            "An error occurred while communicating",
            EXPECTED_WATER_LEVEL,
        ),
        (
            AqvifyAuthException,
            "Authentication failed",
            "unavailable",
        ),
    ],
    ids=["timeout_error", "communications_error", "auth_error"],
)
async def test_coordinator_get_devices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    log_message: str,
    expected_state: str,
) -> None:
    """Tests that the coordinator handles errors from async_get_devices."""

    await setup_integration(hass, mock_config_entry)

    mock_aqvify_client.async_get_devices.side_effect = exception

    caplog.clear()
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == STATE_UNAVAILABLE
    assert log_message in caplog.text

    mock_aqvify_client.async_get_devices.side_effect = None
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == expected_state


@pytest.mark.parametrize(
    ("exception", "log_message", "expected_state"),
    [
        (TimeoutError, "Timeout occurred while communicating", EXPECTED_WATER_LEVEL),
        (
            ClientResponseError(Mock(), Mock(), status=500),
            "An error occurred while communicating",
            EXPECTED_WATER_LEVEL,
        ),
        (AqvifyAuthException, "Invalid API key.", "unavailable"),
    ],
    ids=["timeout_error", "communications_error", "auth_error"],
)
async def test_coordinator_get_device_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    log_message: str,
    expected_state: str,
) -> None:
    """Tests that the coordinator handles errors from async_get_device_latest_data."""

    await setup_integration(hass, mock_config_entry)

    mock_aqvify_client.async_get_device_latest_data.side_effect = exception

    caplog.clear()
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == STATE_UNAVAILABLE
    assert log_message in caplog.text
    mock_aqvify_client.async_get_device_latest_data.side_effect = None
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == expected_state


@pytest.mark.parametrize(
    ("exception", "log_message", "expected_state"),
    [
        (TimeoutError, "Timeout occurred while communicating", EXPECTED_IN_FLOW),
        (
            ClientResponseError(Mock(), Mock(), status=500),
            "An error occurred while communicating",
            EXPECTED_IN_FLOW,
        ),
        (AqvifyAuthException, "Invalid API key.", "unavailable"),
    ],
    ids=["timeout_error", "communications_error", "auth_error"],
)
async def test_coordinator_async_get_hour_aggregation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    log_message: str,
    expected_state: str,
) -> None:
    """Tests that the coordinator handles errors from async_get_hour_aggregation."""

    await setup_integration(hass, mock_config_entry)

    mock_aqvify_client.async_get_hour_aggregation.side_effect = exception

    caplog.clear()
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(IN_FLOW_SENSOR).state == STATE_UNAVAILABLE
    assert log_message in caplog.text
    mock_aqvify_client.async_get_hour_aggregation.side_effect = None
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(IN_FLOW_SENSOR).state == expected_state
