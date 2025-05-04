"""Test the Xiaomi BLE events."""

import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import make_advertisement

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    BluetoothServiceInfoBleak,
    inject_bluetooth_service_info,
)


@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "54:EF:44:E3:9C:BC",
            make_advertisement(
                "54:EF:44:E3:9C:BC",
                b'XY\x97\td\xbc\x9c\xe3D\xefT" `\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3',
            ),
            "5b51a7c91cde6707c9ef18dfda143a58",
            [
                {
                    "entity": "event.smoke_detector_9cbc_button",
                    ATTR_FRIENDLY_NAME: "Smoke Detector 9CBC Button",
                    ATTR_EVENT_TYPE: "press",
                }
            ],
        ),
        (
            "DC:ED:83:87:12:73",
            make_advertisement(
                "DC:ED:83:87:12:73",
                b"XYI\x19Os\x12\x87\x83\xed\xdc\x0b48\n\x02\x00\x00\x8dI\xae(",
            ),
            "b93eb3787eabda352edd94b667f5d5a9",
            [
                {
                    "entity": "event.switch_double_button_1273_button_right",
                    ATTR_FRIENDLY_NAME: "Switch (double button) 1273 Button right",
                    ATTR_EVENT_TYPE: "press",
                }
            ],
        ),
        (
            "F8:24:41:E9:50:74",
            make_advertisement(
                "F8:24:41:E9:50:74",
                b"P0S\x01?tP\xe9A$\xf8\x01\x10\x03\x04\x00\x02",
            ),
            None,
            [
                {
                    "entity": "event.remote_control_5074_button_m",
                    ATTR_FRIENDLY_NAME: "Remote Control 5074 Button M",
                    ATTR_EVENT_TYPE: "long_press",
                }
            ],
        ),
        (
            "F8:24:41:E9:50:74",
            make_advertisement(
                "F8:24:41:E9:50:74",
                b"P0S\x01?tP\xe9A$\xf8\x01\x10\x03\x03\x00\x00",
            ),
            None,
            [
                {
                    "entity": "event.remote_control_5074_button_plus",
                    ATTR_FRIENDLY_NAME: "Remote Control 5074 Button plus",
                    ATTR_EVENT_TYPE: "press",
                }
            ],
        ),
        (
            "DE:70:E8:B2:39:0C",
            make_advertisement(
                "DE:70:E8:B2:39:0C",
                b"@0\xdd\x03$\x03\x00\x01\x01",
            ),
            None,
            [
                {
                    "entity": "event.nightlight_390c_motion",
                    ATTR_FRIENDLY_NAME: "Nightlight 390C Motion",
                    ATTR_EVENT_TYPE: "motion_detected",
                }
            ],
        ),
        (
            "E2:53:30:E6:D3:54",
            make_advertisement(
                "E2:53:30:E6:D3:54",
                b"P0\xe1\x04\x8eT\xd3\xe60S\xe2\x01\x10\x03\x01\x00\x00",
            ),
            None,
            [
                {
                    "entity": "event.magic_cube_d354_cube",
                    ATTR_FRIENDLY_NAME: "Magic Cube D354 Cube",
                    ATTR_EVENT_TYPE: "rotate_left",
                }
            ],
        ),
        (
            "F8:24:41:C5:98:8B",
            make_advertisement(
                "F8:24:41:C5:98:8B",
                b"X0\xb6\x036\x8b\x98\xc5A$\xf8\x8b\xb8\xf2f\x13Q\x00\x00\x00\xd6",
            ),
            "b853075158487ca39a5b5ea9",
            [
                {
                    "entity": "event.dimmer_switch_988b_dimmer",
                    ATTR_FRIENDLY_NAME: "Dimmer Switch 988B Dimmer",
                    ATTR_EVENT_TYPE: "rotate_left",
                    "event_properties": {"steps": 1},
                }
            ],
        ),
        (
            "F8:24:41:C5:98:8B",
            make_advertisement(
                "F8:24:41:C5:98:8B",
                b"X0\xb6\x03\xd2\x8b\x98\xc5A$\xf8\xc3I\x14vu~\x00\x00\x00\x99",
            ),
            "b853075158487ca39a5b5ea9",
            [
                {
                    "entity": "event.dimmer_switch_988b_dimmer",
                    ATTR_FRIENDLY_NAME: "Dimmer Switch 988B Dimmer",
                    ATTR_EVENT_TYPE: "press",
                    "event_properties": {"duration": 2},
                }
            ],
        ),
    ],
)
async def test_events(
    hass: HomeAssistant,
    mac_address: str,
    advertisement: BluetoothServiceInfoBleak,
    bind_key: str | None,
    result: list[dict[str, str]],
) -> None:
    """Test the different Xiaomi BLE events."""
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
        state = hass.states.get(meas["entity"])
        attributes = state.attributes
        assert attributes[ATTR_FRIENDLY_NAME] == meas[ATTR_FRIENDLY_NAME]
        assert attributes[ATTR_EVENT_TYPE] == meas[ATTR_EVENT_TYPE]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are restored
    for meas in result:
        state = hass.states.get(meas["entity"])
        assert state != STATE_UNAVAILABLE

    # Now inject again
    inject_bluetooth_service_info(
        hass,
        advertisement,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        state = hass.states.get(meas["entity"])
        attributes = state.attributes
        assert attributes[ATTR_FRIENDLY_NAME] == meas[ATTR_FRIENDLY_NAME]
        assert attributes[ATTR_EVENT_TYPE] == meas[ATTR_EVENT_TYPE]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_fingerprint(hass: HomeAssistant) -> None:
    """Make sure that fingerprint reader events are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="D7:1F:44:EB:8A:91",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_advertisement(
            "D7:1F:44:EB:8A:91",
            b"PD\x9e\x06B\x91\x8a\xebD\x1f\xd7\x06\x00\x05\xff\xff\xff\xff\x00",
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    sensor = hass.states.get("sensor.door_lock_8a91_key_id")
    sensor_attr = sensor.attributes
    assert sensor.state == "unknown operator"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Key id"

    binary_sensor = hass.states.get("binary_sensor.door_lock_8a91_fingerprint")
    binary_sensor_attribtes = binary_sensor.attributes
    assert binary_sensor.state == STATE_ON
    assert binary_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Fingerprint"

    event = hass.states.get("event.door_lock_8a91_fingerprint")
    event_attr = event.attributes
    assert event_attr[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Fingerprint"
    assert event_attr[ATTR_EVENT_TYPE] == "match_successful"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_xiaomi_lock(hass: HomeAssistant) -> None:
    """Make sure that lock events are correctly mapped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="D7:1F:44:EB:8A:91",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_advertisement(
            "D7:1F:44:EB:8A:91",
            b"PD\x9e\x06C\x91\x8a\xebD\x1f\xd7\x0b\x00\t \x02\x00\x01\x80|D/a",
        ),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    event = hass.states.get("event.door_lock_8a91_lock")
    event_attr = event.attributes
    assert event_attr[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Lock"
    assert event_attr[ATTR_EVENT_TYPE] == "unlock_outside_the_door"

    sensor = hass.states.get("sensor.door_lock_8a91_lock_method")
    sensor_attr = sensor.attributes
    assert sensor.state == "biometrics"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Lock method"

    sensor = hass.states.get("sensor.door_lock_8a91_key_id")
    sensor_attr = sensor.attributes
    assert sensor.state == "Fingerprint key id 2"
    assert sensor_attr[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Key id"

    binary_sensor = hass.states.get("binary_sensor.door_lock_8a91_lock")
    binary_sensor_attribtes = binary_sensor.attributes
    assert binary_sensor.state == STATE_ON
    assert binary_sensor_attribtes[ATTR_FRIENDLY_NAME] == "Door Lock 8A91 Lock"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
