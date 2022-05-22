"""Test KNX notify."""

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import NotifySchema
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_notify_simple(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX notify can send to one device."""
    await knx.setup_integration(
        {
            NotifySchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/0/0",
            }
        }
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify", "notify", {"target": "test", "message": "I love KNX"}, blocking=True
    )

    await knx.assert_write(
        "1/0/0",
        (
            0x49,
            0x20,
            0x6C,
            0x6F,
            0x76,
            0x65,
            0x20,
            0x4B,
            0x4E,
            0x58,
            0x0,
            0x0,
            0x0,
            0x0,
        ),
    )

    await hass.services.async_call(
        "notify",
        "notify",
        {
            "target": "test",
            "message": "I love KNX, but this text is too long for KNX, poor KNX",
        },
        blocking=True,
    )

    await knx.assert_write(
        "1/0/0",
        (
            0x49,
            0x20,
            0x6C,
            0x6F,
            0x76,
            0x65,
            0x20,
            0x4B,
            0x4E,
            0x58,
            0x2C,
            0x20,
            0x62,
            0x75,
        ),
    )


async def test_notify_multiple_sends_to_all_with_different_encodings(
    hass: HomeAssistant, knx: KNXTestKit
):
    """Test KNX notify `type` configuration."""
    await knx.setup_integration(
        {
            NotifySchema.PLATFORM: [
                {
                    CONF_NAME: "ASCII",
                    KNX_ADDRESS: "1/0/0",
                    CONF_TYPE: "string",
                },
                {
                    CONF_NAME: "Latin-1",
                    KNX_ADDRESS: "1/0/1",
                    CONF_TYPE: "latin_1",
                },
            ]
        }
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify", "notify", {"message": "Gänsefüßchen"}, blocking=True
    )

    await knx.assert_write(
        "1/0/0",
        # "G?nsef??chen"
        (71, 63, 110, 115, 101, 102, 63, 63, 99, 104, 101, 110, 0, 0),
    )
    await knx.assert_write(
        "1/0/1",
        (71, 228, 110, 115, 101, 102, 252, 223, 99, 104, 101, 110, 0, 0),
    )
