"""Test function in __init__.py."""
from unittest.mock import patch

from homeassistant.components.mysensors import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAYS,
    CONF_PERSISTENCE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_VERSION,
    DOMAIN,
    async_setup,
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


async def attempt_import(hass: HomeAssistantType, config: ConfigType, expected_calls=1):
    """Test importing a gateway."""
    with patch("sys.platform", "win32"), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await async_setup(hass, config)
        assert result
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == expected_calls
    return mock_setup_entry.call_args


async def test_import_serial(hass: HomeAssistantType):
    """Test importing a serial gateway."""
    args, _ = await attempt_import(
        hass,
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
    )
    # check result
    # we check in this weird way bc there may be some extra keys that we don't care about
    wanted = {
        CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
        CONF_DEVICE: "COM5",
        CONF_PERSISTENCE_FILE: "bla.json",
        CONF_BAUD_RATE: 57600,
        CONF_VERSION: "2.3",
    }
    for key, value in wanted.items():
        assert key in args[1].data
        assert args[1].data[key] == value


async def test_import_tcp(hass: HomeAssistantType):
    """Test importing a tcp gateway."""
    args, _ = await attempt_import(
        hass,
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
    )
    # check result
    # we check in this weird way bc there may be some extra keys that we don't care about
    wanted = {
        CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
        CONF_DEVICE: "127.0.0.1",
        CONF_PERSISTENCE_FILE: "blub.pickle",
        CONF_TCP_PORT: 343,
        CONF_VERSION: "2.4",
    }
    for key, value in wanted.items():
        assert key in args[1].data
        assert args[1].data[key] == value


async def test_import_mqtt(hass: HomeAssistantType):
    """Test importing a mqtt gateway."""
    args, _ = await attempt_import(
        hass,
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
                CONF_VERSION: "2.4",
                CONF_PERSISTENCE: False,
                CONF_RETAIN: False,
            }
        },
        1,
    )
    # check result
    # we check in this weird way bc there may be some extra keys that we don't care about
    wanted = {
        CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
        CONF_DEVICE: "mqtt",
        CONF_VERSION: "2.4",
        CONF_TOPIC_OUT_PREFIX: "outtopic",
        CONF_TOPIC_IN_PREFIX: "intopic",
    }
    for key, value in wanted.items():
        assert key in args[1].data
        assert args[1].data[key] == value


async def test_import_two(hass: HomeAssistantType):
    """Test import two gateways at once."""
    await attempt_import(
        hass,
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
        2,
    )
