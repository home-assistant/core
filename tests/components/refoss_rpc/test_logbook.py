"""The tests for refoss_rpc logbook."""

from unittest.mock import Mock

from homeassistant.components.refoss_rpc.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_REFOSS_CLICK,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import set_integration

from tests.components.logbook.common import MockRow, mock_humanify


async def test_click_event_rpc_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_rpc_device: Mock
) -> None:
    """Test  refoss_rpc click event for rpc device."""
    entry = await set_integration(hass)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_REFOSS_CLICK,
                {
                    ATTR_DEVICE_ID: device.id,
                    ATTR_DEVICE: "test1",
                    ATTR_CLICK_TYPE: "button_single_push",
                    ATTR_CHANNEL: 1,
                },
            ),
            MockRow(
                EVENT_REFOSS_CLICK,
                {
                    ATTR_DEVICE_ID: "no_device_id",
                    ATTR_DEVICE: "test2",
                    ATTR_CLICK_TYPE: "button_down",
                    ATTR_CHANNEL: 1,
                },
            ),
        ],
    )

    assert event1["name"] == "Refoss"
    assert event1["domain"] == DOMAIN
    assert (
        event1["message"]
        == "'button_single_push' click event for test input Input was fired"
    )

    assert event2["name"] == "Refoss"
    assert event2["domain"] == DOMAIN
    assert (
        event2["message"]
        == "'button_down' click event for test2 channel 1 Input was fired"
    )
