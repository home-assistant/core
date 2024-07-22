"""Tests for the Mastodon integration."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonError, MastodonUnauthorizedError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.mastodon.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (MastodonUnauthorizedError, ConfigEntryState.SETUP_ERROR),
        (MastodonError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_initialization_failure(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test initialization failure."""
    mock_mastodon_client.instance.side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
