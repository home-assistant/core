"""Test BTHome binary sensors."""

import logging
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON

from . import make_advertisement

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "mac_address, advertisement, bind_key, result",
    [
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x02\x10\x01",
            ),
            None,
            [
                {
                    "binary_sensor_entity": "binary_sensor.test_device_18b2_power",
                    "friendly_name": "Test Device 18B2 Power",
                    "expected_state": STATE_ON,
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x02\x11\x00",
            ),
            None,
            [
                {
                    "binary_sensor_entity": "binary_sensor.test_device_18b2_opening",
                    "friendly_name": "Test Device 18B2 Opening",
                    "expected_state": STATE_OFF,
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x02\x0F\x01",
            ),
            None,
            [
                {
                    "binary_sensor_entity": "binary_sensor.test_device_18b2_generic",
                    "friendly_name": "Test Device 18B2 Generic",
                    "expected_state": STATE_ON,
                },
            ],
        ),
    ],
)
async def test_binary_sensors(
    hass,
    mac_address,
    advertisement,
    bind_key,
    result,
):
    """Test the different binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    saved_callback(
        advertisement,
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(result)
    for meas in result:
        binary_sensor = hass.states.get(meas["binary_sensor_entity"])
        binary_sensor_attr = binary_sensor.attributes
        assert binary_sensor.state == meas["expected_state"]
        assert binary_sensor_attr[ATTR_FRIENDLY_NAME] == meas["friendly_name"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
