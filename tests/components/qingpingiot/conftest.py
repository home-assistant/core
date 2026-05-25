"""Common fixtures for the qingpingiot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.qingpingiot import DOMAIN
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

TEST_MAC = "AABBCCDDEEFF"
TEST_MODEL = "cgr1w"
TEST_NAME = "Qingping Test Device"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qingpingiot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_MAC,
        data={
            CONF_MAC: TEST_MAC,
            CONF_MODEL: TEST_MODEL,
            CONF_NAME: TEST_NAME,
        },
        title=TEST_NAME,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the qingpingiot integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
