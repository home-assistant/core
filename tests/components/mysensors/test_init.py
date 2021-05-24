"""Test function in __init__.py."""
from __future__ import annotations

from typing import Any
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    "config, expected_calls, expected_to_succeed, expected_config_entry_data",
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
            [
                {
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                    CONF_DEVICE: "COM5",
                    CONF_PERSISTENCE_FILE: "bla.json",
                    CONF_BAUD_RATE: 57600,
                    CONF_VERSION: "2.3",
                    CONF_TCP_PORT: 5003,
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_RETAIN: True,
                }
            ],
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
            [
                {
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                    CONF_DEVICE: "127.0.0.1",
                    CONF_PERSISTENCE_FILE: "blub.pickle",
                    CONF_TCP_PORT: 343,
                    CONF_VERSION: "2.4",
                    CONF_BAUD_RATE: 115200,
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_RETAIN: False,
                }
            ],
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
            [
                {
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                    CONF_DEVICE: "127.0.0.1",
                    CONF_TCP_PORT: 5003,
                    CONF_VERSION: DEFAULT_VERSION,
                    CONF_BAUD_RATE: 115200,
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_RETAIN: False,
                    CONF_PERSISTENCE_FILE: "mysensors1.pickle",
                }
            ],
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
            [
                {
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                    CONF_DEVICE: "mqtt",
                    CONF_VERSION: DEFAULT_VERSION,
                    CONF_BAUD_RATE: 115200,
                    CONF_TCP_PORT: 5003,
                    CONF_TOPIC_OUT_PREFIX: "outtopic",
                    CONF_TOPIC_IN_PREFIX: "intopic",
                    CONF_RETAIN: False,
                    CONF_PERSISTENCE_FILE: "mysensors1.pickle",
                }
            ],
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
            [{}],
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
            [
                {
                    CONF_DEVICE: "mqtt",
                    CONF_PERSISTENCE_FILE: "bla.json",
                    CONF_TOPIC_OUT_PREFIX: "out",
                    CONF_TOPIC_IN_PREFIX: "in",
                    CONF_BAUD_RATE: 115200,
                    CONF_TCP_PORT: 5003,
                    CONF_VERSION: "2.4",
                    CONF_RETAIN: False,
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                },
                {
                    CONF_DEVICE: "COM6",
                    CONF_PERSISTENCE_FILE: "bla2.json",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_BAUD_RATE: 115200,
                    CONF_TCP_PORT: 5003,
                    CONF_VERSION: "2.4",
                    CONF_RETAIN: False,
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                },
            ],
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
            [{}],
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
            [{}],
        ),
        (
            {
                DOMAIN: {
                    CONF_GATEWAYS: [
                        {
                            CONF_DEVICE: "COM1",
                        },
                        {
                            CONF_DEVICE: "COM2",
                        },
                    ],
                }
            },
            2,
            True,
            [
                {
                    CONF_DEVICE: "COM1",
                    CONF_PERSISTENCE_FILE: "mysensors1.pickle",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_BAUD_RATE: 115200,
                    CONF_TCP_PORT: 5003,
                    CONF_VERSION: "1.4",
                    CONF_RETAIN: True,
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                },
                {
                    CONF_DEVICE: "COM2",
                    CONF_PERSISTENCE_FILE: "mysensors2.pickle",
                    CONF_TOPIC_OUT_PREFIX: "",
                    CONF_TOPIC_IN_PREFIX: "",
                    CONF_BAUD_RATE: 115200,
                    CONF_TCP_PORT: 5003,
                    CONF_VERSION: "1.4",
                    CONF_RETAIN: True,
                    CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                },
            ],
        ),
    ],
)
async def test_import(
    hass: HomeAssistant,
    mqtt: None,
    config: ConfigType,
    expected_calls: int,
    expected_to_succeed: bool,
    expected_config_entry_data: list[dict[str, Any]],
) -> None:
    """Test importing a gateway."""
    await async_setup_component(hass, "persistent_notification", {})
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

    for idx in range(expected_calls):
        config_entry = mock_setup_entry.mock_calls[idx][1][1]
        expected_persistence_file = expected_config_entry_data[idx].pop(
            CONF_PERSISTENCE_FILE
        )
        expected_persistence_path = hass.config.path(expected_persistence_file)
        config_entry_data = dict(config_entry.data)
        persistence_path = config_entry_data.pop(CONF_PERSISTENCE_FILE)
        assert persistence_path == expected_persistence_path
        assert config_entry_data == expected_config_entry_data[idx]
