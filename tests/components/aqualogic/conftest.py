"""Fixtures for the AquaLogic integration tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aqualogic import AquaLogicProcessor
from homeassistant.components.aqualogic.const import DOMAIN, UPDATE_TOPIC
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

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
    """Return a mock AquaLogic panel with realistic sensor values."""
    panel = MagicMock()
    panel.is_metric = True
    panel.air_temp = 25.5
    panel.pool_temp = 28.0
    panel.spa_temp = 30.0
    panel.pool_chlorinator = 50.0
    panel.spa_chlorinator = 50.0
    panel.salt_level = 3.5
    panel.pump_speed = 100.0
    panel.pump_power = 1000.0
    panel.status = "OK"
    panel.get_state.return_value = True
    return panel


@pytest.fixture
def mock_aqualogic_device() -> Generator[MagicMock]:
    """Return a mock AquaLogic device that immediately triggers the data callback."""
    with patch(
        "homeassistant.components.aqualogic.config_flow.AquaLogic"
    ) as mock_al_class:

        def _fake_process(callback: object) -> None:
            callback(mock_al_class.return_value)

        mock_al_class.return_value.process.side_effect = _fake_process
        yield mock_al_class


@pytest.fixture
def mock_processor(hass: HomeAssistant, mock_panel: MagicMock) -> Generator[MagicMock]:
    """Mock the AquaLogic processor thread."""
    with patch(
        "homeassistant.components.aqualogic.AquaLogicProcessor"
    ) as mock_processor_class:
        processor = mock_processor_class.return_value
        processor.panel = mock_panel
        processor.data_changed.side_effect = lambda _: dispatcher_send(
            hass, UPDATE_TOPIC
        )
        yield processor


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


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR, Platform.SWITCH]


@pytest.fixture
async def processor_run(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[tuple[AquaLogicProcessor, MagicMock]]:
    """Provide a real AquaLogicProcessor for testing run() without starting the thread."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.aqualogic.RECONNECT_INTERVAL", timedelta(0)),
        patch("homeassistant.components.aqualogic.AquaLogic") as mock_al,
        patch("homeassistant.components.aqualogic.PLATFORMS", []),
        patch("homeassistant.components.aqualogic.AquaLogicProcessor.start"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry.runtime_data, mock_al
