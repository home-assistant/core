"""The tests for the Netgear LTE notify platform."""
from unittest.mock import patch

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.core import HomeAssistant

ICON_PATH = "/some/path"
MESSAGE = "one, two, testing, testing"


async def test_notify(hass: HomeAssistant, setup_integration: None) -> None:
    """Test sending a message."""
    assert hass.services.has_service(NOTIFY_DOMAIN, "netgear_lm1200")

    with patch("homeassistant.components.netgear_lte.eternalegypt.Modem.sms") as mock:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "netgear_lm1200",
            {
                ATTR_MESSAGE: MESSAGE,
                ATTR_TARGET: "5555555556",
            },
            blocking=True,
        )
    assert len(mock.mock_calls) == 1
