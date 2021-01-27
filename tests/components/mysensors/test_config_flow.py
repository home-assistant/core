"""Test the MySensors config flow."""
from typing import Dict
from unittest.mock import patch

import voluptuous as vol

from homeassistant import config_entries, setup
from homeassistant.components.mysensors import async_setup
from homeassistant.components.mysensors.config_flow import MySensorsConfigFlowHandler
from homeassistant.components.mysensors.const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_GATEWAYS,
    CONF_PERSISTENCE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    ConfGatewayType,
)
from homeassistant.components.mysensors.gateway import is_serial_port
from homeassistant.helpers.typing import ConfigType, HomeAssistantType


async def get_form(
    hass: HomeAssistantType, gatway_type: ConfGatewayType, expected_step_id: str
):
    """Get a form for the given gateway type."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    stepuser = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert stepuser["type"] == "form"
    assert not stepuser["errors"]

    actualstep = await hass.config_entries.flow.async_configure(
        stepuser["flow_id"],
        {CONF_GATEWAY_TYPE: gatway_type},
    )
    await hass.async_block_till_done()
    assert actualstep["type"] == "form"
    assert actualstep["step_id"] == expected_step_id

    return actualstep


async def test_config_mqtt(hass: HomeAssistantType):
    """Test configuring a mqtt gateway."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_MQTT, "gw_mqtt")
    flowid = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flowid,
            {
                CONF_RETAIN: True,
                CONF_TOPIC_IN_PREFIX: "bla",
                CONF_TOPIC_OUT_PREFIX: "blub",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result2:
        assert not result2["errors"]
    assert result2["type"] == "create_entry"
    assert result2["title"] == "mqtt"
    assert result2["data"] == {
        CONF_DEVICE: "mqtt",
        CONF_RETAIN: True,
        CONF_TOPIC_IN_PREFIX: "bla",
        CONF_TOPIC_OUT_PREFIX: "blub",
        CONF_VERSION: "2.4",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


def test_is_serial_port_windows(hass: HomeAssistantType):
    """Test windows serial ports."""
    tests = {
        "COM5": True,
        "asdf": False,
        "COM17": True,
        "COM": False,
        "/dev/ttyACM0": False,
    }

    def testport(port, result):
        try:
            is_serial_port(port)
        except vol.Invalid:
            success = False
        else:
            success = True
        assert success == result

    with patch("sys.platform", "win32"):
        for test, result in tests.items():
            testport(test, result)


async def test_config_serial(hass: HomeAssistantType):
    """Test configuring a gateway via serial."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_SERIAL, "gw_serial")
    flowid = step["flow_id"]

    with patch(  # mock is_serial_port because otherwise the test will be platform dependent (/dev/ttyACMx vs COMx)
        "homeassistant.components.mysensors.config_flow.is_serial_port",
        return_value=True,
    ), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flowid,
            {
                CONF_BAUD_RATE: 115200,
                CONF_DEVICE: "/dev/ttyACM0",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result2:
        assert not result2["errors"]
    assert result2["type"] == "create_entry"
    assert result2["title"] == "/dev/ttyACM0"
    assert result2["data"] == {
        CONF_DEVICE: "/dev/ttyACM0",
        CONF_BAUD_RATE: 115200,
        CONF_VERSION: "2.4",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_tcp(hass: HomeAssistantType):
    """Test configuring a gateway via tcp."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_TCP, "gw_tcp")
    flowid = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flowid,
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result2:
        assert not result2["errors"]
    assert result2["type"] == "create_entry"
    assert result2["title"] == "127.0.0.1"
    assert result2["data"] == {
        CONF_DEVICE: "127.0.0.1",
        CONF_TCP_PORT: 5003,
        CONF_VERSION: "2.4",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_fail_to_connect(hass: HomeAssistantType):
    """Test configuring a gateway via tcp."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_TCP, "gw_tcp")
    flowid = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=False
    ), patch(
        "homeassistant.components.mysensors.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flowid,
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert "errors" in result2
    assert "base" in result2["errors"]
    assert result2["errors"]["base"] == "cannot_connect"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def config_invalid(
    hass: HomeAssistantType,
    gatway_type: ConfGatewayType,
    expected_step_id: str,
    user_input: Dict[str, any],
    err_field,
    err_string,
):
    """Perform a test that is expected to generate an error."""
    step = await get_form(hass, gatway_type, expected_step_id)
    flowid = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flowid,
            user_input,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert "errors" in result2
    assert err_field in result2["errors"]
    assert result2["errors"][err_field] == err_string
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_config_tcp_invalid_port(hass: HomeAssistantType):
    """Test invalid port on a tcp gateway."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 60000000,
            CONF_DEVICE: "127.0.0.1",
            CONF_VERSION: "2.4",
        },
        CONF_TCP_PORT,
        "port_out_of_range",
    )


async def test_config_tcp_invalid_port_too_small(hass: HomeAssistantType):
    """Test invalid port on a tcp gateway."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 0,
            CONF_DEVICE: "127.0.0.1",
            CONF_VERSION: "2.4",
        },
        CONF_TCP_PORT,
        "port_out_of_range",
    )


async def test_config_tcp_invalid_version(hass: HomeAssistantType):
    """Test tcp gateway with invalid version."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 5003,
            CONF_DEVICE: "127.0.0.1",
            CONF_VERSION: "a",
        },
        CONF_VERSION,
        "invalid_version",
    )


async def test_config_tcp_invalid_version2(hass: HomeAssistantType):
    """Test tcp gateway with invalid version."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 5003,
            CONF_DEVICE: "127.0.0.1",
            CONF_VERSION: "a.b",
        },
        CONF_VERSION,
        "invalid_version",
    )


async def test_config_tcp_no_version(hass: HomeAssistantType):
    """Test tcp gateway with invalid version."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 5003,
            CONF_DEVICE: "127.0.0.1",
        },
        CONF_VERSION,
        "invalid_version",
    )


async def test_config_tcp_invalid_address(hass: HomeAssistantType):
    """Test tcp gateway with invalid ip address."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_TCP,
        "gw_tcp",
        {
            CONF_TCP_PORT: 5003,
            CONF_DEVICE: "127.0.0.",
            CONF_VERSION: "2.4",
        },
        CONF_DEVICE,
        "invalid_ip",
    )


async def test_config_mqtt_invalid_persistence_file(hass: HomeAssistantType):
    """Test mqtt gateway with invalid input topic."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_MQTT,
        "gw_mqtt",
        {
            CONF_RETAIN: True,
            CONF_TOPIC_IN_PREFIX: "bla",
            CONF_TOPIC_OUT_PREFIX: "blub",
            CONF_PERSISTENCE_FILE: "asdf.zip",
            CONF_VERSION: "2.4",
        },
        CONF_PERSISTENCE_FILE,
        "invalid_persistence_file",
    )


async def test_config_mqtt_invalid_in_topic(hass: HomeAssistantType):
    """Test mqtt gateway with invalid input topic."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_MQTT,
        "gw_mqtt",
        {
            CONF_RETAIN: True,
            CONF_TOPIC_IN_PREFIX: "/#/#",
            CONF_TOPIC_OUT_PREFIX: "blub",
            CONF_VERSION: "2.4",
        },
        CONF_TOPIC_IN_PREFIX,
        "invalid_subscribe_topic",
    )


async def test_config_mqtt_invalid_out_topic(hass: HomeAssistantType):
    """Test mqtt gateway with invalid output topic."""
    await config_invalid(
        hass,
        CONF_GATEWAY_TYPE_MQTT,
        "gw_mqtt",
        {
            CONF_RETAIN: True,
            CONF_TOPIC_IN_PREFIX: "asdf",
            CONF_TOPIC_OUT_PREFIX: "/#/#",
            CONF_VERSION: "2.4",
        },
        CONF_TOPIC_OUT_PREFIX,
        "invalid_publish_topic",
    )


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
    """Test importing a gateway via serial."""
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
    """Test configuring a gateway via serial."""
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
    """Test configuring a gateway via serial."""
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
    """Test configuring a gateway via serial."""
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


async def test_validate_common_none(hass: HomeAssistantType):
    """Test validate common with None."""
    with patch("sys.platform", "win32"), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ):
        handler = MySensorsConfigFlowHandler()
        assert await handler.validate_common(CONF_GATEWAY_TYPE_MQTT) == {}
