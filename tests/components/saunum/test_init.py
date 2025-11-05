"""Test Saunum Leil integration setup and teardown."""

from unittest.mock import patch

from pysaunum import SaunumConnectionError, SaunumException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test integration setup."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test integration unload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.PLATFORMS",
        [Platform.CLIMATE],
    ):
        # Setup first
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # Then unload
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test integration setup fails when connection cannot be established."""
    mock_config_entry.add_to_hass(hass)

    mock_saunum_client.connect.side_effect = SaunumConnectionError("Connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator handles update failures."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now trigger an update failure
    mock_saunum_client.async_get_data.side_effect = SaunumException("Read error")

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()

    # Verify error was logged
    assert "Communication error: Read error" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_device_entry(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry entry."""
    assert (
        device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, "01K98T2T85R5GN0ZHYV25VFMMA")}
        )
    )
    assert device_entry == snapshot
