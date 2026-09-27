"""Test function in gateway.py."""

from unittest.mock import MagicMock, patch

import probatio
import pytest

from homeassistant.components.mysensors.const import CONF_GATEWAY_TYPE_MQTT
from homeassistant.components.mysensors.gateway import (
    MQTT_COMPONENT,
    _get_gateway,
    is_serial_port,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("port", "expect_valid"),
    [
        ("COM5", True),
        ("asdf", False),
        ("COM17", True),
        ("COM", False),
        ("/dev/ttyACM0", False),
    ],
)
def test_is_serial_port_windows(
    hass: HomeAssistant, port: str, expect_valid: bool
) -> None:
    """Test windows serial port."""

    with patch("sys.platform", "win32"):
        try:
            is_serial_port(port)
        except probatio.Invalid:
            assert not expect_valid
        else:
            assert expect_valid


@pytest.mark.usefixtures("mqtt")
async def test_mqtt_gateway(hass: HomeAssistant) -> None:
    """Test the MQTT gateway publishes and subscribes through MQTT."""
    sub_cb = MagicMock()
    with (
        patch(
            "homeassistant.components.mysensors.gateway.mysensors.AsyncMQTTGateway"
        ) as gateway_class,
        patch("homeassistant.components.mqtt.async_publish") as mock_publish,
        patch("homeassistant.components.mqtt.async_subscribe") as mock_subscribe,
    ):
        gateway = await _get_gateway(
            hass,
            gateway_type=CONF_GATEWAY_TYPE_MQTT,
            device=MQTT_COMPONENT,
            version="2.3",
            event_callback=MagicMock(),
            topic_in_prefix="in",
            topic_out_prefix="out",
            persistence=False,
        )
        pub_callback, sub_callback = gateway_class.call_args.args
        pub_callback("out/1", "payload", 0, False)
        sub_callback("in/1", sub_cb, 0)
        await hass.async_block_till_done()

    assert gateway is gateway_class.return_value
    mock_publish.assert_called_once_with(hass, "out/1", "payload", 0, False)
    assert mock_subscribe.call_args.args[:2] == (hass, "in/1")
    message_callback = mock_subscribe.call_args.args[2]
    message_callback(MagicMock(topic="in/1", payload="value", qos=0))
    sub_cb.assert_called_once_with("in/1", "value", 0)
