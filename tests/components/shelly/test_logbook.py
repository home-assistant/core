"""The tests for Shelly logbook."""

from unittest.mock import Mock

from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get as async_get_dev_reg,
)
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_shelly_click_event_block_device(
    hass: HomeAssistant, mock_block_device: Mock
) -> None:
    """Test humanifying Shelly click event for block device."""
    entry = await init_integration(hass, 1)
    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, entry.entry_id)[0]

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_SHELLY_CLICK,
                {
                    ATTR_DEVICE_ID: device.id,
                    ATTR_DEVICE: "shellyix3-12345678",
                    ATTR_CLICK_TYPE: "single",
                    ATTR_CHANNEL: 1,
                },
            ),
            MockRow(
                EVENT_SHELLY_CLICK,
                {
                    ATTR_DEVICE_ID: "no_device_id",
                    ATTR_DEVICE: "shellyswitch25-12345678",
                    ATTR_CLICK_TYPE: "long",
                    ATTR_CHANNEL: 2,
                },
            ),
        ],
    )

    assert event1["name"] == "Shelly"
    assert event1["domain"] == DOMAIN
    assert (
        event1["message"]
        == "'single' click event for Test name channel 1 Input was fired"
    )

    assert event2["name"] == "Shelly"
    assert event2["domain"] == DOMAIN
    assert (
        event2["message"]
        == "'long' click event for shellyswitch25-12345678 channel 2 Input was fired"
    )


async def test_humanify_shelly_click_event_rpc_device(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test humanifying Shelly click event for rpc device."""
    entry = await init_integration(hass, 2)
    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, entry.entry_id)[0]

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_SHELLY_CLICK,
                {
                    ATTR_DEVICE_ID: device.id,
                    ATTR_DEVICE: "shellyplus1pm-12345678",
                    ATTR_CLICK_TYPE: "single_push",
                    ATTR_CHANNEL: 1,
                },
            ),
            MockRow(
                EVENT_SHELLY_CLICK,
                {
                    ATTR_DEVICE_ID: "no_device_id",
                    ATTR_DEVICE: "shellypro4pm-12345678",
                    ATTR_CLICK_TYPE: "btn_down",
                    ATTR_CHANNEL: 2,
                },
            ),
        ],
    )

    assert event1["name"] == "Shelly"
    assert event1["domain"] == DOMAIN
    assert (
        event1["message"]
        == "'single_push' click event for Test name input 0 Input was fired"
    )

    assert event2["name"] == "Shelly"
    assert event2["domain"] == DOMAIN
    assert (
        event2["message"]
        == "'btn_down' click event for shellypro4pm-12345678 channel 2 Input was fired"
    )
