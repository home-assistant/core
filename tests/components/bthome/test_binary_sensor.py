"""Test BTHome binary sensors."""
import logging

import pytest

from homeassistant.components.bthome.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import make_bthome_v1_adv, make_bthome_v2_adv

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
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
            make_bthome_v1_adv(
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
            make_bthome_v1_adv(
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
async def test_v1_binary_sensors(
    hass: HomeAssistant,
    mac_address,
    advertisement,
    bind_key,
    result,
) -> None:
    """Test the different BTHome v1 binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        advertisement,
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


@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x10\x01",
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
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x11\x00",
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
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x0F\x01",
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
async def test_v2_binary_sensors(
    hass: HomeAssistant,
    mac_address,
    advertisement,
    bind_key,
    result,
) -> None:
    """Test the different BTHome v2 binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        advertisement,
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
