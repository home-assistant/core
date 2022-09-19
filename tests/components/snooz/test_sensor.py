"""Test Snooz sensors."""
from __future__ import annotations

from unittest.mock import patch

from pysnooz import commands
import pytest

from homeassistant.components.bluetooth import BluetoothCallback, BluetoothChange
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.snooz import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ADDRESS,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant

from . import TEST_ADDRESS, TEST_PAIRING_TOKEN, SnoozFixture, create_device_with_rssi

from tests.common import MockConfigEntry


async def test_signal_strength(
    hass: HomeAssistant, mock_snooz: SnoozFixture, bluetooth_callback: BluetoothCallback
):
    """Test signal strength sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    bluetooth_callback(create_device_with_rssi(-100), BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    async def _test_signal_strength(rssi: int) -> None:
        bluetooth_callback(create_device_with_rssi(rssi), BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()

        signal_sensor = hass.states.get("sensor.snooz_abcd_signal_strength")
        signal_attributes = signal_sensor.attributes
        assert signal_sensor.state == str(rssi)
        assert signal_attributes[ATTR_FRIENDLY_NAME] == "Snooz ABCD Signal Strength"
        assert signal_attributes[ATTR_UNIT_OF_MEASUREMENT] == "dBm"
        assert signal_attributes[ATTR_STATE_CLASS] == "measurement"

    await _test_signal_strength(-100)
    await _test_signal_strength(-33)
    await _test_signal_strength(-68)


async def test_connection_status(hass: HomeAssistant, mock_snooz: SnoozFixture):
    """Test connection status sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    status_sensor = hass.states.get("sensor.snooz_abcd_connection_status")
    assert status_sensor.state == "disconnected"
    assert (
        status_sensor.attributes[ATTR_FRIENDLY_NAME] == "Snooz ABCD Connection Status"
    )

    # connect by executing a command
    await mock_snooz.data.device.async_execute_command(commands.turn_on())

    status_sensor = hass.states.get("sensor.snooz_abcd_connection_status")
    assert status_sensor.state == "connected"


@pytest.fixture(name="bluetooth_callback")
def fixture_bluetooth_callback() -> BluetoothCallback:
    """Return a callback to call when publishing bluetooth callbacks registered by the snooz integration."""
    saved_callback: BluetoothCallback = lambda _info, _change: None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    def _forward_callback(info, change) -> None:
        nonlocal saved_callback
        saved_callback(info, change)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        yield _forward_callback
