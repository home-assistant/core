"""The tests for hue logbook."""
from homeassistant.components.hue.const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN
from homeassistant.components.hue.v1.hue_event import CONF_LAST_UPDATED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_EVENT,
    CONF_ID,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import setup_platform

from tests.components.logbook.common import MockRow, mock_humanify

# v1 event
SAMPLE_V1_EVENT = {
    CONF_DEVICE_ID: "fe346f17a9f8c15be633f9cc3f3d6631",
    CONF_EVENT: 18,
    CONF_ID: "hue_tap",
    CONF_LAST_UPDATED: "2019-12-28T22:58:03",
    CONF_UNIQUE_ID: "00:00:00:00:00:44:23:08-f2",
}
# v2 event
SAMPLE_V2_EVENT = {
    CONF_DEVICE_ID: "f974028e7933aea703a2199a855bc4a3",
    CONF_ID: "wall_switch_with_2_controls_button",
    CONF_SUBTYPE: 1,
    CONF_TYPE: "initial_press",
    CONF_UNIQUE_ID: "c658d3d8-a013-4b81-8ac6-78b248537e70",
}


async def test_humanify_hue_events(
    hass: HomeAssistant, mock_bridge_v2, device_registry: dr.DeviceRegistry
) -> None:
    """Test hue events when the devices are present in the registry."""
    await setup_platform(hass, mock_bridge_v2, "sensor")
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    v1_device = device_registry.async_get_or_create(
        identifiers={(DOMAIN, "v1")}, name="Remote 1", config_entry_id=entry.entry_id
    )
    v2_device = device_registry.async_get_or_create(
        identifiers={(DOMAIN, "v2")}, name="Remote 2", config_entry_id=entry.entry_id
    )

    (v1_event, v2_event) = mock_humanify(
        hass,
        [
            MockRow(
                ATTR_HUE_EVENT,
                {**SAMPLE_V1_EVENT, CONF_DEVICE_ID: v1_device.id},
            ),
            MockRow(
                ATTR_HUE_EVENT,
                {**SAMPLE_V2_EVENT, CONF_DEVICE_ID: v2_device.id},
            ),
        ],
    )

    assert v1_event["name"] == "Remote 1"
    assert v1_event["domain"] == DOMAIN
    assert v1_event["message"] == "Event 18"

    assert v2_event["name"] == "Remote 2"
    assert v2_event["domain"] == DOMAIN
    assert v2_event["message"] == "first button pressed initially"


async def test_humanify_hue_events_devices_removed(
    hass: HomeAssistant, mock_bridge_v2
) -> None:
    """Test hue events when the devices have been removed from the registry."""
    await setup_platform(hass, mock_bridge_v2, "sensor")
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    (v1_event, v2_event) = mock_humanify(
        hass,
        [
            MockRow(
                ATTR_HUE_EVENT,
                SAMPLE_V1_EVENT,
            ),
            MockRow(
                ATTR_HUE_EVENT,
                SAMPLE_V2_EVENT,
            ),
        ],
    )

    assert v1_event["name"] == "hue_tap"
    assert v1_event["domain"] == DOMAIN
    assert v1_event["message"] == "Event 18"

    assert v2_event["name"] == "wall_switch_with_2_controls_button"
    assert v2_event["domain"] == DOMAIN
    assert v2_event["message"] == "first button pressed initially"
