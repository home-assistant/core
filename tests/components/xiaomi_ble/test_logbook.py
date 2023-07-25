"""The tests for Xiaomi BLE logbook."""
from homeassistant.components.xiaomi_ble.const import (
    DOMAIN,
    XIAOMI_BLE_EVENT,
    XiaomiBleEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_xiaomi_ble_event(hass: HomeAssistant) -> None:
    """Test humanifying xiaomi ble button presses."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="DE:70:E8:B2:39:0C",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    (event1, event2) = mock_humanify(
        hass,
        [
            MockRow(
                XIAOMI_BLE_EVENT,
                dict(
                    XiaomiBleEvent(
                        device_id=None,
                        address="DE:70:E8:B2:39:0C",
                        event_class="button",
                        event_type="long_press",
                        event_properties={
                            "any": "thing",
                        },
                    )
                ),
            ),
            MockRow(
                XIAOMI_BLE_EVENT,
                dict(
                    XiaomiBleEvent(
                        device_id=None,
                        address="DE:70:E8:B2:39:0C",
                        event_class="motion",
                        event_type="motion_detected",
                        event_properties=None,
                    )
                ),
            ),
        ],
    )

    assert event1["name"] == "Xiaomi BLE DE:70:E8:B2:39:0C"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "button long_press: {'any': 'thing'}"

    assert event2["name"] == "Xiaomi BLE DE:70:E8:B2:39:0C"
    assert event2["domain"] == DOMAIN
    assert event2["message"] == "motion motion_detected"
