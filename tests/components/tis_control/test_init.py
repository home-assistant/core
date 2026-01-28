"""Tests for the TIS Control integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tis_control import async_setup_entry, async_unload_entry
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, async_capture_events


# Helper function to mock the infinite async generator for events.
async def _mock_consume_events():
    yield None


@pytest.fixture
def mock_setup_entry():
    """Override async_setup_entry for unload tests."""
    with patch(
        "homeassistant.components.tis_control.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_setup_entry.data = {CONF_PORT: "6000"}
        mock_setup_entry.domain = DOMAIN
        mock_setup_entry.entry_id = "1234"
        mock_setup_entry.runtime_data = MagicMock()
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CN11A1A00001",
        domain=DOMAIN,
        data={CONF_PORT: "6000"},
        unique_id="CN11A1A00001",
    )


@pytest.fixture
def mock_tis_api():
    """Mock the TISApi class."""
    with patch("homeassistant.components.tis_control.TISApi") as mock_cls:
        instance = mock_cls.return_value
        instance.connect = AsyncMock()
        instance.scan_devices = AsyncMock()
        instance.consume_events.side_effect = _mock_consume_events
        yield instance


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_tis_api
) -> None:
    """Test successful setup of entry."""
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_tis_api.connect.assert_called_once()
        mock_tis_api.scan_devices.assert_called_once()
        mock_forward.assert_called_once()
        assert mock_config_entry.runtime_data.tis_api == mock_tis_api


@pytest.mark.asyncio
async def test_async_setup_entry_connect_failure(
    hass: HomeAssistant, mock_config_entry, mock_tis_api
) -> None:
    """Test unsuccessful setup due to connection failure."""
    mock_tis_api.connect.side_effect = ConnectionError("Test error")

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)

    mock_tis_api.scan_devices.assert_not_called()
    mock_forward.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_scan_failure(
    hass: HomeAssistant, mock_config_entry, mock_tis_api
) -> None:
    """Test setup proceeds even if scan_devices fails."""
    mock_tis_api.scan_devices.side_effect = ConnectionError("Scan failed")

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_tis_api.scan_devices.assert_called_once()
        mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_event_listener(
    hass: HomeAssistant, mock_config_entry, mock_tis_api
) -> None:
    """Test that the background task consumes events and fires bus events."""
    fake_event = {"device_id": "test_device", "value": 1}

    # Mock generator that yields one event.
    async def _mock_event_generator():
        yield fake_event

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    # Capture events of the specific type we expect.
    event_type = "tis_device_test_device"
    captured_events = async_capture_events(hass, event_type)

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        await async_setup_entry(hass, mock_config_entry)

        # Wait for background task to process.
        await hass.async_block_till_done()

    # Assert event was fired.
    assert len(captured_events) == 1
    assert captured_events[0].data == fake_event


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test successful unload of entry."""
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_setup_entry)
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test unsuccessful unload of entry."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, mock_setup_entry)

        assert result is False
        mock_unload_platforms.assert_called_once()
