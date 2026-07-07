"""Fixtures for AquaLogic tests."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aqualogic import DOMAIN, AquaLogicProcessor
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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
def mock_processor(mock_panel: MagicMock) -> MagicMock:
    """Return a mock AquaLogicProcessor registered in hass.data."""
    with patch("homeassistant.components.aqualogic.AquaLogicProcessor") as mock_cls:
        processor = MagicMock()
        processor.panel = mock_panel
        mock_cls.return_value = processor
        yield processor


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_panel: MagicMock
) -> AquaLogicProcessor:
    """Set up the AquaLogic integration and run one pass of run() to register the callback.

    AquaLogic is mocked so mock_panel becomes processor.panel. _shutdown is set before
    run() so it exits after a single iteration, registering the data_changed callback
    with panel.process() without starting a real network thread.
    """
    with patch("homeassistant.components.aqualogic.AquaLogic") as mock_al:
        mock_al.return_value = mock_panel
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}},
        )
        await hass.async_block_till_done()
        processor: AquaLogicProcessor = hass.data[DOMAIN]
        processor._shutdown = True
        processor.run()
    return processor


@pytest.fixture
def update_callback(
    init_integration: AquaLogicProcessor, mock_panel: MagicMock
) -> Callable[[], None]:
    """Return a callable that fires a panel data update through the registered callback.

    Extracts the data_changed callback from the mock's process() call args so tests
    trigger updates through the same path as real panel data arriving.
    """
    callback = mock_panel.process.call_args[0][0]
    return lambda: callback(mock_panel)
