"""The tests for the LG webOS TV notify platform."""

from unittest.mock import call

from aiowebostv import WebOsTvCommandError
import pytest

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.components.webostv import DOMAIN
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from . import setup_webostv
from .const import TV_NAME

ICON_PATH = "/some/path"
MESSAGE = "one, two, testing, testing"
SERVICE_NAME = slugify(TV_NAME)


async def test_notify(hass: HomeAssistant, client) -> None:
    """Test sending a message."""
    await setup_webostv(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {
            ATTR_MESSAGE: MESSAGE,
            ATTR_DATA: {
                ATTR_ICON: ICON_PATH,
            },
        },
        blocking=True,
    )
    assert client.mock_calls[0] == call.connect()
    assert client.connect.call_count == 1
    client.send_message.assert_called_with(MESSAGE, icon_path=ICON_PATH)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {
            ATTR_MESSAGE: MESSAGE,
            ATTR_DATA: {
                "OTHER_DATA": "not_used",
            },
        },
        blocking=True,
    )
    assert client.mock_calls[0] == call.connect()
    assert client.connect.call_count == 1
    client.send_message.assert_called_with(MESSAGE, icon_path=None)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {
            ATTR_MESSAGE: "only message, no data",
        },
        blocking=True,
    )

    assert client.connect.call_count == 1
    assert client.send_message.call_args == call(
        "only message, no data", icon_path=None
    )


@pytest.mark.parametrize(
    ("is_on", "exception", "error_message"),
    [
        (
            True,
            WebOsTvCommandError("Some error"),
            f"Communication error while sending notification to device {TV_NAME}: Some error",
        ),
        (
            True,
            FileNotFoundError("Some other error"),
            f"Icon {ICON_PATH} not found when sending notification for device {TV_NAME}",
        ),
        (
            False,
            None,
            f"Error sending notification to device {TV_NAME}: Device is off and cannot be controlled",
        ),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    client,
    is_on: bool,
    exception: Exception,
    error_message: str,
) -> None:
    """Test error scenarios."""
    await setup_webostv(hass)
    client.tv_state.is_on = is_on

    assert hass.services.has_service("notify", SERVICE_NAME)

    client.send_message.side_effect = exception
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            {
                ATTR_MESSAGE: MESSAGE,
                ATTR_DATA: {
                    ATTR_ICON: ICON_PATH,
                },
            },
            blocking=True,
        )

    assert client.send_message.call_count == int(is_on)


async def test_no_discovery_info(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert NOTIFY_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {"notify": {"platform": DOMAIN}},
    )
    await hass.async_block_till_done()
    assert NOTIFY_DOMAIN in hass.config.components
    assert f"Failed to initialize notification service {DOMAIN}" in caplog.text
    assert not hass.services.has_service("notify", SERVICE_NAME)
