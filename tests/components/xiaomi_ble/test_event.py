"""Test the Xiaomi BLE events."""
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
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
                b'XY\x97\td\xbc\x9c\xe3D\xefT" `'
                b"\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3",
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
