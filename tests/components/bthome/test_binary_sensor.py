"""Test BTHome binary sensors."""
from datetime import timedelta
import logging
import time
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import make_bthome_v1_adv, make_bthome_v2_adv

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)

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
                b"\x44\x11\x00",
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


async def test_unavailable(hass: HomeAssistant) -> None:
    """Test normal device goes to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
        data={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_bthome_v2_adv(
            "A4:C1:38:8D:18:B2",
            b"\x40\x11\x01",
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    opening_sensor = hass.states.get("binary_sensor.test_device_18b2_opening")

    assert opening_sensor.state == STATE_ON

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    opening_sensor = hass.states.get("binary_sensor.test_device_18b2_opening")

    # Normal devices should go to unavailable
    assert opening_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sleepy_device(hass: HomeAssistant) -> None:
    """Test sleepy device does not go to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
        data={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_bthome_v2_adv(
            "A4:C1:38:8D:18:B2",
            b"\x44\x11\x01",
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    opening_sensor = hass.states.get("binary_sensor.test_device_18b2_opening")

    assert opening_sensor.state == STATE_ON

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    opening_sensor = hass.states.get("binary_sensor.test_device_18b2_opening")

    # Sleepy devices should keep their state over time
    assert opening_sensor.state == STATE_ON

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
