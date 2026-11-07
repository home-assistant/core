"""Test the rtl_433 integration setup and unload."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.rtl_433.const import CONF_SECURE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_PATH, MOCK_PORT, MOCK_UNIQUE_ID

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a hub entry loads, registers the hub device, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert hub_device is not None
    assert hub_device.manufacturer == "rtl_433"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_rtl433_client.return_value.stop.assert_awaited()


async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test the entry retries when the server never connects (test-before-setup)."""
    mock_rtl433_client.return_value.connected = False

    with patch("homeassistant.components.rtl_433.coordinator._CONNECT_TIMEOUT", 0.0):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("version", "minor_version", "expected_state"),
    [
        pytest.param(2, 7, ConfigEntryState.LOADED, id="current_schema"),
        pytest.param(2, 1, ConfigEntryState.LOADED, id="older_minor"),
        pytest.param(2, 8, ConfigEntryState.LOADED, id="newer_minor"),
        pytest.param(1, 1, ConfigEntryState.MIGRATION_ERROR, id="version_1"),
    ],
)
@pytest.mark.usefixtures("mock_rtl433_client")
async def test_migrate_entry(
    hass: HomeAssistant,
    version: int,
    minor_version: int,
    expected_state: ConfigEntryState,
) -> None:
    """Test every version 2 schema loads and version 1 is refused."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"rtl_433 ({MOCK_HOST})",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
        unique_id=MOCK_UNIQUE_ID,
        version=version,
        minor_version=minor_version,
    )

    await setup_integration(hass, entry)

    assert entry.state is expected_state
