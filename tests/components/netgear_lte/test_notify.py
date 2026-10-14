"""The tests for the Netgear LTE notify platform."""

from unittest.mock import patch

import eternalegypt
import pytest

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ICON_PATH = "/some/path"
MESSAGE = "one, two, testing, testing"
TARGET = "5555555556"


async def test_notify(hass: HomeAssistant, setup_integration: None) -> None:
    """Test sending a message."""
    assert hass.services.has_service(NOTIFY_DOMAIN, "netgear_lm1200")

    with patch("homeassistant.components.netgear_lte.eternalegypt.Modem.sms") as mock:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "netgear_lm1200",
            {
                ATTR_MESSAGE: MESSAGE,
                ATTR_TARGET: TARGET,
            },
            blocking=True,
        )
    assert len(mock.mock_calls) == 1


@pytest.mark.usefixtures("setup_integration")
async def test_notify_error(hass: HomeAssistant) -> None:
    """Test that a failed send raises an error with a translation key."""
    with (
        patch(
            "homeassistant.components.netgear_lte.eternalegypt.Modem.sms",
            side_effect=eternalegypt.Error,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "netgear_lm1200",
            {
                ATTR_MESSAGE: MESSAGE,
                ATTR_TARGET: TARGET,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "send_message_failed"
    assert exc_info.value.translation_placeholders == {"target": TARGET}
