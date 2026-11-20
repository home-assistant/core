"""The tests for notify_events."""

from pytest_homeassistant.common import async_mock_service

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyServiceArgument,
)
from homeassistant.components.notify_events.notify import (
    ATTR_LEVEL,
    ATTR_PRIORITY,
    ATTR_TOKEN,
)
from homeassistant.core import HomeAssistant


async def test_send_msg(hass: HomeAssistant) -> None:
    """Test notify.events service."""
    notify_calls = async_mock_service(hass, NOTIFY_DOMAIN, "events")

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "events",
        {
            NotifyServiceArgument.MESSAGE: "message content",
            NotifyServiceArgument.DATA: {
                ATTR_TOKEN: "XYZ",
                ATTR_LEVEL: "warning",
                ATTR_PRIORITY: "high",
            },
        },
        blocking=True,
    )

    assert len(notify_calls) == 1
    call = notify_calls[-1]

    assert call.domain == NOTIFY_DOMAIN
    assert call.service == "events"
    assert call.data.get(NotifyServiceArgument.MESSAGE) == "message content"
    assert call.data.get(NotifyServiceArgument.DATA).get(ATTR_TOKEN) == "XYZ"
    assert call.data.get(NotifyServiceArgument.DATA).get(ATTR_LEVEL) == "warning"
    assert call.data.get(NotifyServiceArgument.DATA).get(ATTR_PRIORITY) == "high"
