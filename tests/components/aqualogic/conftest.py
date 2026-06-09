"""Fixtures for the AquaLogic integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aqualogic.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
        entry_id="test_aqualogic_entry",
    )


@pytest.fixture
def mock_panel() -> MagicMock:
    """Return a mock AquaLogic panel."""
    panel = MagicMock()
    panel.is_metric = True
    panel.air_temp = 25.5
    panel.pool_temp = 27.8
    panel.spa_temp = 38.0
    panel.pool_chlorinator = 50
    panel.spa_chlorinator = 0
    panel.salt_level = 3.3
    panel.pump_speed = 60
    panel.pump_power = 850
    panel.status = "OK"
    panel.get_state.return_value = True
    return panel


@pytest.fixture
def mock_processor(mock_panel: MagicMock) -> Generator[MagicMock]:
    """Mock the AquaLogic processor thread."""
    with patch(
        "homeassistant.components.aqualogic.AquaLogicProcessor"
    ) as mock_processor_class:
        processor = mock_processor_class.return_value
        processor.panel = mock_panel
        yield processor


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR, Platform.SWITCH]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_processor: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the AquaLogic integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.aqualogic.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
