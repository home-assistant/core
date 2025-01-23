"""Test KNX notify."""

from homeassistant.components import notify
from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import NotifySchema
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_notify_simple(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX notify can send to one device."""
    await knx.setup_integration(
        {
            NotifySchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/0/0",
            }
        }
    )
    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": "notify.test",
            notify.ATTR_MESSAGE: "I love KNX",
        },
    )
    await knx.assert_write(
        "1/0/0",
        (73, 32, 108, 111, 118, 101, 32, 75, 78, 88, 0, 0, 0, 0),
    )

    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": "notify.test",
            notify.ATTR_MESSAGE: "I love KNX, but this text is too long for KNX, poor KNX",
        },
    )
    await knx.assert_write(
        "1/0/0",
        (73, 32, 108, 111, 118, 101, 32, 75, 78, 88, 44, 32, 98, 117),
    )


async def test_notify_multiple_sends_with_different_encodings(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
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
    message = {notify.ATTR_MESSAGE: "Gänsefüßchen"}

    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": "notify.ascii",
            **message,
        },
    )
    await knx.assert_write(
        "1/0/0",
        # "G?nsef??chen"
        (71, 63, 110, 115, 101, 102, 63, 63, 99, 104, 101, 110, 0, 0),
    )

    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": "notify.latin_1",
            **message,
        },
    )
    await knx.assert_write(
        "1/0/1",
        (71, 228, 110, 115, 101, 102, 252, 223, 99, 104, 101, 110, 0, 0),
    )
