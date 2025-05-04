"""Provide common fixtures."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

from pybalboa.enums import HeatMode, LowHighRange
import pytest

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


@pytest.fixture(name="integration")
async def integration_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the balboa integration."""
    return await init_integration(hass)


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
    """Mock balboa spa client."""
    with patch(
        "homeassistant.components.balboa.SpaClient", autospec=True
    ) as mock_balboa:
        client = mock_balboa.return_value
        callback: list[Callable] = []

        def on(_, _callback: Callable):
            callback.append(_callback)
            return lambda: None

        def emit(_):
            for _cb in callback:
                _cb()

        client.on.side_effect = on
        client.emit.side_effect = emit

        client.model = "FakeSpa"
        client.mac_address = "ef:ef:ef:c0:ff:ee"
        client.software_version = "M0 V0.0"

        client.blowers = []
        client.circulation_pump.state = 0
        client.filter_cycle_1_running = False
        client.filter_cycle_1_start = time(8, 0)
        client.filter_cycle_1_end = time(9, 0)
        client.filter_cycle_2_running = False
        client.filter_cycle_2_enabled = True
        client.filter_cycle_2_start = time(19, 0)
        client.filter_cycle_2_end = time(21, 30)
        client.temperature_unit = 1
        client.temperature = 10
        client.temperature_minimum = 10
        client.temperature_maximum = 40
        client.target_temperature = 40
        client.heat_mode.state = HeatMode.READY
        client.heat_mode.set_state = AsyncMock()
        client.heat_mode.options = list(HeatMode)[:2]
        client.heat_state = 2
        client.lights = []
        client.pumps = []
        client.temperature_range.state = LowHighRange.LOW

        client.fault = None

        yield client
