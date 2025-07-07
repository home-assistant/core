"""Test Homee initialization."""

from unittest.mock import MagicMock

from pyHomee import HomeeAuthFailedException, HomeeConnectionFailedException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homee.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import build_mock_node, setup_integration
from .conftest import HOMEE_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_eff", "config_entry_state", "active_flows"),
    [
        (
            HomeeConnectionFailedException("connection timed out"),
            ConfigEntryState.SETUP_RETRY,
            [],
        ),
        (
            HomeeAuthFailedException("wrong username or password"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth"],
        ),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_eff: Exception,
    config_entry_state: ConfigEntryState,
    active_flows: list[str],
) -> None:
    """Test if connection errors on startup are handled correctly."""
    mock_homee.get_access_token.side_effect = side_eff
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is config_entry_state

    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == active_flows


async def test_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("homee.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    await mock_homee.add_connection_listener.call_args_list[0][0][0](False)
    await hass.async_block_till_done()
    assert "Disconnected from Homee" in caplog.text
    await mock_homee.add_connection_listener.call_args_list[0][0][0](True)
    await hass.async_block_till_done()
    assert "Reconnected to Homee" in caplog.text


async def test_general_data(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test if data is set correctly."""
    mock_homee.nodes = [
        build_mock_node("cover_with_position_slats.json"),
        build_mock_node("homee.json"),
    ]
    mock_homee.get_node_by_id = (
        lambda node_id: mock_homee.nodes[0] if node_id == 3 else mock_homee.nodes[1]
    )
    await setup_integration(hass, mock_config_entry)

    # Verify hub and device created correctly using snapshots.
    hub = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}")})
    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})

    assert hub == snapshot
    assert device == snapshot


async def test_software_version(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sw_version for device with only AttributeType.SOFTWARE_VERSION."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})
    assert device.sw_version == "1.45"


async def test_invalid_profile(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test unknown value passed to get_name_for_enum."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]
    # This is a profile, that does not exist in the enum.
    mock_homee.nodes[0].profile = 77
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, f"{HOMEE_ID}-3")})
    assert device.model is None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading of config entry."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
