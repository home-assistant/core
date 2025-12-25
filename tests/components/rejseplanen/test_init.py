"""Tests for rejseplanen __init__ setup entry behavior."""

from unittest.mock import patch

import pytest

from homeassistant.components.rejseplanen import async_setup_entry
from homeassistant.components.rejseplanen.coordinator import (
    RejseplanenDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry_raises_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """If the coordinator first refresh fails, setup should raise ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    # Patch the coordinator's first refresh to raise an error (simulate API/down)
    with (
        patch.object(
            RejseplanenDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            side_effect=Exception("API down"),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)
