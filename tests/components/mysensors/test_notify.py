"""Provide tests for mysensors notify platform."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_text_type(
    hass: HomeAssistant,
    text_node: Sensor,
    transport_write: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test a text type child."""
    # Test without target.
    await hass.services.async_call(
        NOTIFY_DOMAIN, "mysensors", {"message": "Hello World"}, blocking=True
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;0;47;Hello World\n")

    # Test with target.
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "mysensors",
        {"message": "Hello", "target": "Text Node 1 1"},
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args == call("1;1;1;0;47;Hello\n")

    transport_write.reset_mock()

    # Test a message longer than 25 characters.
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "mysensors",
        {
            "message": "This is a long message that will be split",
            "target": "Text Node 1 1",
        },
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list == [
        call("1;1;1;0;47;This is a long message th\n"),
        call("1;1;1;0;47;at will be split\n"),
    ]


async def test_text_type_discovery(
    hass: HomeAssistant,
    text_node: Sensor,
    transport_write: MagicMock,
    receive_message: Callable[[str], None],
) -> None:
    """Test text type discovery."""
    receive_message("1;2;0;0;36;\n")
    receive_message("1;2;1;0;47;test\n")
    receive_message("1;2;1;0;47;test2\n")  # Test that more than one set message works.
    await hass.async_block_till_done()

    # Test targeting the discovered child.
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "mysensors",
        {"message": "Hello", "target": "Text Node 1 2"},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;2;1;0;47;Hello\n")

    transport_write.reset_mock()

    # Test targeting all notify children.
    await hass.services.async_call(
        NOTIFY_DOMAIN, "mysensors", {"message": "Hello World"}, blocking=True
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list == [
        call("1;1;1;0;47;Hello World\n"),
        call("1;2;1;0;47;Hello World\n"),
    ]
