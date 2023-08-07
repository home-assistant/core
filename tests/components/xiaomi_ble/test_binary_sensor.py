"""Test Xiaomi binary sensors."""

from datetime import timedelta
import time
from unittest.mock import patch

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.xiaomi_ble.const import CONF_SLEEPY_DEVICE, DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import make_advertisement

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
)


async def test_door_problem_sensors(hass: HomeAssistant) -> None:
    """Test setting up a door binary sensor with additional problem sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="EE:89:73:44:BE:98",
        data={"bindkey": "2c3795afa33019a8afdc17ba99e6f217"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "EE:89:73:44:BE:98",
            b"HU9\x0e3\x9cq\xc0$\x1f\xff\xee\x80S\x00\x00\x02\xb4\xc59",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    door_sensor = hass.states.get("binary_sensor.door_lock_be98_door")
    door_sensor_attribtes = door_sensor.attributes
    assert door_sensor.state == STATE_OFF
    assert door_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Door Lock BE98 Door"

    door_left_open = hass.states.get("binary_sensor.door_lock_be98_door_left_open")
    door_left_open_attribtes = door_left_open.attributes
    assert door_left_open.state == STATE_OFF
    assert (
        door_left_open_attribtes[ATTR_FRIENDLY_NAME] == "Door Lock BE98 Door left open"
    )

    pry_the_door = hass.states.get("binary_sensor.door_lock_be98_pry_the_door")
    pry_the_door_attribtes = pry_the_door.attributes
    assert pry_the_door.state == STATE_OFF
    assert pry_the_door_attribtes[ATTR_FRIENDLY_NAME] == "Door Lock BE98 Pry the door"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_light_motion(hass: HomeAssistant) -> None:
    """Test setting up a light and motion binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:35:93:21",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "58:2D:34:35:93:21",
            b"P \xf6\x07\xda!\x9354-X\x0f\x00\x03\x01\x00\x00",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    motion_sensor = hass.states.get("binary_sensor.nightlight_9321_motion")
    motion_sensor_attribtes = motion_sensor.attributes
    assert motion_sensor.state == STATE_ON
    assert motion_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Nightlight 9321 Motion"

    light_sensor = hass.states.get("binary_sensor.nightlight_9321_light")
    light_sensor_attribtes = light_sensor.attributes
    assert light_sensor.state == STATE_OFF
    assert light_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Nightlight 9321 Light"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_moisture(hass: HomeAssistant) -> None:
    """Test setting up a moisture binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C4:7C:8D:6A:3E:7A",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1014, payload len is 0x2 and payload is 0xf400
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "C4:7C:8D:6A:3E:7A", b"q \x5d\x01iz>j\x8d|\xc4\r\x14\x10\x02\xf4\x00"
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    sensor = hass.states.get("binary_sensor.smart_flower_pot_3e7a_moisture")
    sensor_attr = sensor.attributes
    assert sensor.state == STATE_ON
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Smart Flower Pot 3E7A Moisture"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_opening(hass: HomeAssistant) -> None:
    """Test setting up a opening binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:66:E5:67",
        data={"bindkey": "0fdcc30fe9289254876b5ef7c11ef1f0"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "A4:C1:38:66:E5:67",
            b"XY\x89\x18\x9ag\xe5f8\xc1\xa4\x9d\xd9z\xf3&\x00\x00\xc8\xa6\x0b\xd5",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")
    opening_sensor_attribtes = opening_sensor.attributes

    assert opening_sensor.state == STATE_ON
    assert (
        opening_sensor_attribtes[ATTR_FRIENDLY_NAME]
        == "Door/Window Sensor E567 Opening"
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_opening_problem_sensors(hass: HomeAssistant) -> None:
    """Test setting up a opening binary sensor with additional problem sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:66:E5:67",
        data={"bindkey": "0fdcc30fe9289254876b5ef7c11ef1f0"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "A4:C1:38:66:E5:67",
            b"XY\x89\x18ug\xe5f8\xc1\xa4i\xdd\xf3\xa1&\x00\x00\xa2J\x1bE",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")
    opening_sensor_attribtes = opening_sensor.attributes
    assert opening_sensor.state == STATE_OFF
    assert (
        opening_sensor_attribtes[ATTR_FRIENDLY_NAME]
        == "Door/Window Sensor E567 Opening"
    )

    door_left_open = hass.states.get(
        "binary_sensor.door_window_sensor_e567_door_left_open"
    )
    door_left_open_attribtes = door_left_open.attributes
    assert door_left_open.state == STATE_OFF
    assert (
        door_left_open_attribtes[ATTR_FRIENDLY_NAME]
        == "Door/Window Sensor E567 Door left open"
    )

    device_forcibly_removed = hass.states.get(
        "binary_sensor.door_window_sensor_e567_device_forcibly_removed"
    )
    device_forcibly_removed_attribtes = device_forcibly_removed.attributes
    assert device_forcibly_removed.state == STATE_OFF
    assert (
        device_forcibly_removed_attribtes[ATTR_FRIENDLY_NAME]
        == "Door/Window Sensor E567 Device forcibly removed"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_smoke(hass: HomeAssistant) -> None:
    """Test setting up a smoke binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:EF:44:E3:9C:BC",
        data={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "54:EF:44:E3:9C:BC",
            b"XY\x97\tf\xbc\x9c\xe3D\xefT\x01\x08\x12\x05\x00\x00\x00q^\xbe\x90",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    smoke_sensor = hass.states.get("binary_sensor.smoke_detector_9cbc_smoke")
    smoke_sensor_attribtes = smoke_sensor.attributes
    assert smoke_sensor.state == STATE_ON
    assert smoke_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Smoke Detector 9CBC Smoke"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unavailable(hass: HomeAssistant) -> None:
    """Test normal device goes to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:66:E5:67",
        data={"bindkey": "0fdcc30fe9289254876b5ef7c11ef1f0"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "A4:C1:38:66:E5:67",
            b"XY\x89\x18\x9ag\xe5f8\xc1\xa4\x9d\xd9z\xf3&\x00\x00\xc8\xa6\x0b\xd5",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")

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

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")

    # Normal devices should go to unavailable
    assert opening_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_SLEEPY_DEVICE not in entry.data


async def test_sleepy_device(hass: HomeAssistant) -> None:
    """Test sleepy device does not go to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:66:E5:67",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            "A4:C1:38:66:E5:67",
            b"@0\xd6\x03$\x19\x10\x01\x00",
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")

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

    opening_sensor = hass.states.get("binary_sensor.door_window_sensor_e567_opening")

    # Sleepy devices should keep their state over time
    assert opening_sensor.state == STATE_ON

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_SLEEPY_DEVICE] is True
