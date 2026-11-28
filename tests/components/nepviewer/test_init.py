"""Test the NEPViewer integration setup."""

from unittest.mock import MagicMock

from aionepviewer import NepApiError, NepAuthError, NepConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nepviewer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.usefixtures("mock_nepviewer")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a config entry can be set up and unloaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("method", ["get_sites", "get_site_overview"])
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            NepAuthError,
            ConfigEntryState.SETUP_ERROR,
            id="auth_failure_setup_error",
        ),
        pytest.param(
            NepConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="connection_error_setup_retry",
        ),
        pytest.param(
            NepApiError(500, "error"),
            ConfigEntryState.SETUP_RETRY,
            id="api_error_setup_retry",
        ),
    ],
)
async def test_setup_entry_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    method: str,
    side_effect: Exception | type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup fails gracefully on API errors."""
    getattr(mock_nepviewer, method).side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the registered devices and how they are linked."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices = {
        name: device_registry.async_get_device_by_identifier(
            (DOMAIN, identifier), mock_config_entry.entry_id
        )
        for name, identifier in (
            ("site", "test_sid"),
            ("gateway", "TEST_SN"),
            ("panel", "TEST_SN_1"),
        )
    }
    assert devices == snapshot


@pytest.mark.parametrize("side_effect", [NepConnectionError, NepApiError(500, "error")])
async def test_site_detail_is_optional(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    side_effect: Exception | type[Exception],
) -> None:
    """Test that setup succeeds without the site details."""
    mock_nepviewer.get_site_detail.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_gateway_of_unknown_site(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
) -> None:
    """Test that a gateway is set up when its site is not listed."""
    mock_nepviewer.get_sites.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, "TEST_SN"), mock_config_entry.entry_id
    )
    assert gateway is not None
    assert gateway.via_device_id is None
