"""Tests for the Acmeda hub module."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiopulse
import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.components.acmeda.hub import PulseHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def pulse_hub(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> PulseHub:
    """Return a PulseHub instance."""
    return PulseHub(hass, mock_config_entry)


async def test_title_when_api_is_none(pulse_hub: PulseHub) -> None:
    """Test title property returns host when api is None."""
    pulse_hub.api = None
    assert pulse_hub.title == "127.0.0.1"


async def test_title_when_api_is_set(pulse_hub: PulseHub) -> None:
    """Test title property returns formatted id and host when api is set."""
    mock_api = MagicMock()
    mock_api.id = "hub-id"
    mock_api.host = "127.0.0.1"
    pulse_hub.api = mock_api
    assert pulse_hub.title == "hub-id (127.0.0.1)"


async def test_host_returns_config_entry_host(pulse_hub: PulseHub) -> None:
    """Test host property returns host from config entry."""
    assert pulse_hub.host == "127.0.0.1"


async def test_async_start_returns_early_when_api_is_none(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_start returns early when api is None."""
    pulse_hub.api = None
    await pulse_hub.async_start()
    # Should not raise and should not call anything


async def test_async_start_runs_api_when_api_is_set(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_start calls api.run() when api is set."""
    mock_api = AsyncMock()
    pulse_hub.api = mock_api
    await pulse_hub.async_start()
    mock_api.run.assert_called_once()


async def test_async_reset_returns_false_when_api_is_none(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_reset returns False when api is None."""
    pulse_hub.api = None
    result = await pulse_hub.async_reset()
    assert result is False


async def test_async_reset_returns_true_when_api_is_set(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_reset returns True when api is set."""
    mock_api = AsyncMock()
    mock_api.callback_unsubscribe = MagicMock()
    pulse_hub.api = mock_api
    result = await pulse_hub.async_reset()
    assert result is True
    mock_api.callback_unsubscribe.assert_called_once()
    mock_api.stop.assert_called_once()


async def test_async_notify_update_returns_early_when_api_is_none(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_notify_update returns early when api is None."""
    pulse_hub.api = None
    await pulse_hub.async_notify_update(aiopulse.UpdateType.rollers)
    # Should not raise and should not call anything


async def test_async_notify_update_updates_devices_when_api_is_set(
    hass: HomeAssistant, pulse_hub: PulseHub, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_notify_update updates devices when api is set and update_type is rollers."""
    mock_api = MagicMock()
    mock_api.rollers = {}
    pulse_hub.api = mock_api

    with patch("homeassistant.components.acmeda.hub.update_devices") as mock_update:
        await pulse_hub.async_notify_update(aiopulse.UpdateType.rollers)
        mock_update.assert_called_once_with(
            hass, mock_config_entry, mock_api.rollers
        )


async def test_async_notify_update_does_nothing_for_non_rollers_update(
    hass: HomeAssistant, pulse_hub: PulseHub
) -> None:
    """Test async_notify_update does nothing for non-rollers update type."""
    mock_api = MagicMock()
    pulse_hub.api = mock_api

    with patch("homeassistant.components.acmeda.hub.update_devices") as mock_update:
        await pulse_hub.async_notify_update(aiopulse.UpdateType.automation)
        mock_update.assert_not_called()
