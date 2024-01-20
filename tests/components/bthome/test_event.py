"""Test the BTHome sensors."""
import logging

import pytest

from homeassistant.components.bthome.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import make_bthome_v2_adv

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3A\x00\x3A\x01\x3A\x03",
            ),
            None,
            [
                {
                    "event_entity": "event.test_device_18b2_button_3",
                    "friendly_name": "Test Device 18B2 Button 3",
                    "expected_state": STATE_UNKNOWN,
                },
                {
                    "event_entity": "event.test_device_18b2_button_4",
                    "friendly_name": "Test Device 18B2 Button 4",
                    "expected_state": STATE_UNKNOWN,
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3A\x04",
            ),
            None,
            [
                {
                    "event_entity": "event.test_device_18b2_button",
                    "friendly_name": "Test Device 18B2 Button",
                    "expected_state": STATE_UNKNOWN,
                }
            ],
        ),
    ],
)
async def test_v2_events(
    hass: HomeAssistant,
    mac_address,
    advertisement,
    bind_key,
    result,
) -> None:
    """Test the different BTHome V2 events."""
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
        sensor = hass.states.get(meas["event_entity"])
        sensor_attr = sensor.attributes
        assert sensor.state == meas["expected_state"]
        assert sensor_attr[ATTR_FRIENDLY_NAME] == meas["friendly_name"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
