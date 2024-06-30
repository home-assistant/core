"""Test the flume init."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms_fixture() -> Generator[list[str]]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.flume.PLATFORMS", []):
        yield


async def test_setup_config_entry(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
    access_token: None,
    device_list: None,
) -> None:
    """Test load and unload of a ConfigEntry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
