"""Tests for the Elke27 integration setup."""

from unittest.mock import MagicMock

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
    InvalidCredentials,
)
import pytest

from homeassistant.components.elke27.const import (
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device = dr.async_get(hass).async_get_device({(DOMAIN, "1234")})
    assert device is not None
    assert device.manufacturer == "Elk Products"
    assert device.name == "Panel"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        pytest.param(Elke27TimeoutError(), ConfigEntryState.SETUP_RETRY, id="timeout"),
        pytest.param(
            Elke27ConnectionError(), ConfigEntryState.SETUP_RETRY, id="connection"
        ),
        pytest.param(
            Elke27LinkRequiredError(),
            ConfigEntryState.SETUP_ERROR,
            id="link-required",
        ),
        pytest.param(
            InvalidCredentials(),
            ConfigEntryState.SETUP_ERROR,
            id="invalid-credentials",
        ),
    ],
)
async def test_setup_connect_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test connection errors during setup set the matching entry state."""
    mock_client.async_connect.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    mock_client.async_disconnect.assert_awaited_once()


async def test_setup_retries_when_panel_not_ready(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a readiness timeout puts the entry in setup retry."""
    mock_client.wait_ready.return_value = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_client")
async def test_setup_invalid_link_keys(hass: HomeAssistant) -> None:
    """Test invalid stored link keys fail setup as an auth error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: "not-link-keys",
            CONF_CLIENT_ID: "112233445566",
        },
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retries_when_first_refresh_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed first refresh retries setup and disconnects the client."""
    mock_client.async_refresh_csm.side_effect = Elke27TimeoutError()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_disconnect.assert_awaited_once()


async def test_setup_retries_when_snapshot_missing(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a missing snapshot after refresh retries setup."""
    mock_client.get_snapshot.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_disconnect.assert_awaited_once()
