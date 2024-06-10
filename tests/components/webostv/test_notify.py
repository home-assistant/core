"""The tests for the WebOS TV notify platform."""

from unittest.mock import Mock, call

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.components.webostv import DOMAIN
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import TV_NAME

ICON_PATH = "/some/path"
MESSAGE = "one, two, testing, testing"


async def test_notify(hass: HomeAssistant, client) -> None:
    """Test sending a message."""
    await setup_webostv(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, TV_NAME)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        TV_NAME,
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
        TV_NAME,
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
        TV_NAME,
        {
            ATTR_MESSAGE: "only message, no data",
        },
        blocking=True,
    )

    assert client.connect.call_count == 1
    assert client.send_message.call_args == call(
        "only message, no data", icon_path=None
    )


async def test_notify_not_connected(hass: HomeAssistant, client, monkeypatch) -> None:
    """Test sending a message when client is not connected."""
    await setup_webostv(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, TV_NAME)

    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        TV_NAME,
        {
            ATTR_MESSAGE: MESSAGE,
            ATTR_DATA: {
                ATTR_ICON: ICON_PATH,
            },
        },
        blocking=True,
    )
    assert client.mock_calls[0] == call.connect()
    assert client.connect.call_count == 2
    client.send_message.assert_called_with(MESSAGE, icon_path=ICON_PATH)


async def test_icon_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, client, monkeypatch
) -> None:
    """Test notify icon not found error."""
    await setup_webostv(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, TV_NAME)

    monkeypatch.setattr(client, "send_message", Mock(side_effect=FileNotFoundError))
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        TV_NAME,
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
    assert f"Icon {ICON_PATH} not found" in caplog.text


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WebOsTvPairError, "Pairing with TV failed"),
        (ConnectionRefusedError, "TV unreachable"),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    client,
    monkeypatch,
    side_effect,
    error,
) -> None:
    """Test connection errors scenarios."""
    await setup_webostv(hass)
    assert hass.services.has_service("notify", TV_NAME)

    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=side_effect))
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        TV_NAME,
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
    client.send_message.assert_not_called()
    assert error in caplog.text


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
    assert not hass.services.has_service("notify", TV_NAME)
