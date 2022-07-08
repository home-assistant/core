"""Tests for the Bluetooth integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.models import HaBleakScanner
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.generated import bluetooth as bt_gen
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_bleak_scanner():
    """Fixture to mock starting the bleak scanner."""

    class MockedBleakScanner(HaBleakScanner):
        """Mocked BleakScanner."""

        async def start(self):
            """Start the scanner."""
            pass

    with patch(
        "homeassistant.components.bluetooth.HaBleakScanner",
        side_effect=MockedBleakScanner,
    ) as mock_bleak_scanner:
        yield mock_bleak_scanner


async def test_setup(hass, mock_bleak_scanner):
    """Test configured options for a device are loaded via config entry."""
    mock_bt = [
        {"domain": "switchbot", "service_uuid": "cba20d00-224d-11e6-9fb8-0002a5d5c51b"}
    ]
    with patch.object(bt_gen, "BLUETOOTH", mock_bt), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow:
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_bleak_scanner.mock_calls) == 1
    expected_flow_calls = 0
    for matching_components in mock_bt:
        domains = set()
        for component in matching_components:
            if len(component) == 1:
                domains.add(component["domain"])
        expected_flow_calls += len(domains)
    assert len(mock_config_flow.mock_calls) == expected_flow_calls
