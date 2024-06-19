"""The tests for bthome logbook."""

from homeassistant.components.bthome.const import (
    BTHOME_BLE_EVENT,
    DOMAIN,
    BTHomeBleEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_bthome_event(hass: HomeAssistant) -> None:
    """Test humanifying bthome button presses."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    (event1, event2) = mock_humanify(
        hass,
        [
            MockRow(
                BTHOME_BLE_EVENT,
                dict(
                    BTHomeBleEvent(
                        device_id=None,
                        address="A4:C1:38:8D:18:B2",
                        event_class="button",
                        event_type="long_press",
                        event_properties={
                            "any": "thing",
                        },
                    )
                ),
            ),
            MockRow(
                BTHOME_BLE_EVENT,
                dict(
                    BTHomeBleEvent(
                        device_id=None,
                        address="A4:C1:38:8D:18:B2",
                        event_class="button",
                        event_type="press",
                        event_properties=None,
                    )
                ),
            ),
        ],
    )

    assert event1["name"] == "BTHome A4:C1:38:8D:18:B2"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "button long_press: {'any': 'thing'}"

    assert event2["name"] == "BTHome A4:C1:38:8D:18:B2"
    assert event2["domain"] == DOMAIN
    assert event2["message"] == "button press"
