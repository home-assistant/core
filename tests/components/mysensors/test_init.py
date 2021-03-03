"""Test function in __init__.py."""
from typing import Dict
from unittest.mock import patch

import pytest

from homeassistant.components.mysensors import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAYS,
    CONF_PERSISTENCE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_VERSION,
    DEFAULT_VERSION,
    DOMAIN,
)
from homeassistant.components.mysensors.const import (
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    "config, expected_calls, expected_to_succeed, expected_config_flow_user_input",
    [
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "COM5",
                            CONF_PERSISTENCE_FILE: "bla.json",
                            CONF_BAUD_RATE: 57600,
                            CONF_TCP_PORT: 5003,
                        }
                    ],
                    CONF_VERSION: "2.3",
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: True,
                }
            },
            1,
            True,
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_PERSISTENCE_FILE: "bla.json",
                CONF_BAUD_RATE: 57600,
                CONF_VERSION: "2.3",
            },
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "127.0.0.1",
                            CONF_PERSISTENCE_FILE: "blub.pickle",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 343,
                        }
                    ],
                    CONF_VERSION: "2.4",
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            1,
            True,
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "127.0.0.1",
                CONF_PERSISTENCE_FILE: "blub.pickle",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.4",
            },
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "127.0.0.1",
                        }
                    ],
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            1,
            True,
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "127.0.0.1",
                CONF_TCP_PORT: 5003,
                CONF_VERSION: DEFAULT_VERSION,
            },
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "mqtt",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                            CONF_TOPIC_IN_PREFIX: "intopic",
                            CONF_TOPIC_OUT_PREFIX: "outtopic",
                        }
                    ],
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            1,
            True,
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: DEFAULT_VERSION,
                CONF_TOPIC_OUT_PREFIX: "outtopic",
                CONF_TOPIC_IN_PREFIX: "intopic",
            },
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "mqtt",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        }
                    ],
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            0,
            True,
            {},
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "mqtt",
                            CONF_PERSISTENCE_FILE: "bla.json",
                            CONF_TOPIC_OUT_PREFIX: "out",
                            CONF_TOPIC_IN_PREFIX: "in",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        },
                        {
                            CONF_DEVICE: "COM6",
                            CONF_PERSISTENCE_FILE: "bla2.json",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        },
                    ],
                    CONF_VERSION: "2.4",
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            2,
            True,
            {},
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "mqtt",
                            CONF_PERSISTENCE_FILE: "bla.json",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        },
                        {
                            CONF_DEVICE: "COM6",
                            CONF_PERSISTENCE_FILE: "bla.json",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        },
                    ],
                    CONF_VERSION: "2.4",
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            0,
            False,
            {},
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "COMx",
                            CONF_PERSISTENCE_FILE: "bla.json",
                            CONF_BAUD_RATE: 115200,
                            CONF_TCP_PORT: 5003,
                        },
                    ],
                    CONF_VERSION: "2.4",
                    CONF_PERSISTENCE: False,
                    CONF_RETAIN: False,
                }
            },
            0,
            True,
            {},
        ),
    ],
)
async def test_import(
    hass: HomeAssistantType,
    config: ConfigType,
    expected_calls: int,
    expected_to_succeed: bool,
    expected_config_flow_user_input: Dict[str, any],
):
    """Test importing a gateway."""
    with patch("sys.platform", "win32"), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await async_setup_component(hass, DOMAIN, config)
        assert result == expected_to_succeed
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == expected_calls

    if expected_calls > 0:
        config_flow_user_input = mock_setup_entry.mock_calls[0][1][1].data
        for key, value in expected_config_flow_user_input.items():
            assert key in config_flow_user_input
            assert config_flow_user_input[key] == value
