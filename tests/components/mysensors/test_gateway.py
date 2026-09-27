"""Test function in gateway.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import probatio
import pytest

from homeassistant.components.mysensors.const import (
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_RETAIN,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
)
from homeassistant.components.mysensors.gateway import is_serial_port
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


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


async def test_mqtt_gateway(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the MQTT gateway subscribes and publishes through MQTT."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
            CONF_DEVICE: "mqtt",
            CONF_VERSION: "2.3",
            CONF_TOPIC_IN_PREFIX: "in",
            CONF_TOPIC_OUT_PREFIX: "out",
            CONF_RETAIN: False,
        },
    )
    entry.add_to_hass(hass)
    with (
        patch("mysensors.task.OTAFirmware", autospec=True),
        patch("mysensors.task.load_fw", autospec=True),
        patch("mysensors.task.Persistence", autospec=True) as persistence_class,
    ):
        persistence = persistence_class.return_value
        persistence.schedule_save_sensors = AsyncMock()
        persistence.safe_load_sensors = MagicMock()
        persistence.save_sensors = MagicMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        subscribed_topics = [
            call.args[0] for call in mqtt_mock.async_subscribe.call_args_list
        ]
        assert "in/+/+/3/+/+" in subscribed_topics

        # A time request is answered by publishing the current time
        async_fire_mqtt_message(hass, "in/1/255/3/0/1", "")
        await hass.async_block_till_done()

    published_topics = [call.args[0] for call in mqtt_mock.async_publish.call_args_list]
    assert "out/1/255/3/0/1" in published_topics
