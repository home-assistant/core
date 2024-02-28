"""Test the BTHome events."""

import pytest

from homeassistant.components.bthome.const import DOMAIN
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import make_bthome_v2_adv

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    BluetoothServiceInfoBleak,
    inject_bluetooth_service_info,
)


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
                    "entity": "event.test_device_18b2_button_2",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button 2",
                    ATTR_EVENT_TYPE: "press",
                },
                {
                    "entity": "event.test_device_18b2_button_3",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button 3",
                    ATTR_EVENT_TYPE: "triple_press",
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
                    "entity": "event.test_device_18b2_button",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button",
                    ATTR_EVENT_TYPE: "long_press",
                }
            ],
        ),
    ],
)
async def test_v2_events(
    hass: HomeAssistant,
    mac_address: str,
    advertisement: BluetoothServiceInfoBleak,
    bind_key: str | None,
    result: list[dict[str, str]],
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
