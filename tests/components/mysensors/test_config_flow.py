"""Test the MySensors config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mysensors.const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    ConfGatewayType,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry

GATEWAY_TYPE_TO_STEP = {
    CONF_GATEWAY_TYPE_TCP: "gw_tcp",
    CONF_GATEWAY_TYPE_SERIAL: "gw_serial",
    CONF_GATEWAY_TYPE_MQTT: "gw_mqtt",
}


async def get_form(
    hass: HomeAssistant, gateway_type: ConfGatewayType, expected_step_id: str
) -> FlowResult:
    """Get a form for the given gateway type."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": GATEWAY_TYPE_TO_STEP[gateway_type]}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == expected_step_id

    return result


async def test_config_mqtt(hass: HomeAssistant, mqtt: None) -> None:
    """Test configuring a mqtt gateway."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_MQTT, "gw_mqtt")
    flow_id = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_RETAIN: True,
                CONF_TOPIC_IN_PREFIX: "bla",
                CONF_TOPIC_OUT_PREFIX: "blub",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result:
        assert not result["errors"]
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "mqtt"
    assert result["data"] == {
        CONF_DEVICE: "mqtt",
        CONF_RETAIN: True,
        CONF_TOPIC_IN_PREFIX: "bla",
        CONF_TOPIC_OUT_PREFIX: "blub",
        CONF_VERSION: "2.4",
        CONF_GATEWAY_TYPE: "MQTT",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_missing_mqtt(hass: HomeAssistant) -> None:
    """Test configuring a mqtt gateway without mqtt integration setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": GATEWAY_TYPE_TO_STEP[CONF_GATEWAY_TYPE_MQTT]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "mqtt_required"


async def test_config_serial(hass: HomeAssistant) -> None:
    """Test configuring a gateway via serial."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_SERIAL, "gw_serial")
    flow_id = step["flow_id"]

    with patch(  # mock is_serial_port because otherwise the test will be platform dependent (/dev/ttyACMx vs COMx)
        "homeassistant.components.mysensors.config_flow.is_serial_port",
        return_value=True,
    ), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_BAUD_RATE: 115200,
                CONF_DEVICE: "/dev/ttyACM0",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result:
        assert not result["errors"]
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/ttyACM0"
    assert result["data"] == {
        CONF_DEVICE: "/dev/ttyACM0",
        CONF_BAUD_RATE: 115200,
        CONF_VERSION: "2.4",
        CONF_GATEWAY_TYPE: "Serial",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_tcp(hass: HomeAssistant) -> None:
    """Test configuring a gateway via tcp."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_TCP, "gw_tcp")
    flow_id = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    if "errors" in result:
        assert not result["errors"]
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.1"
    assert result["data"] == {
        CONF_DEVICE: "127.0.0.1",
        CONF_TCP_PORT: 5003,
        CONF_VERSION: "2.4",
        CONF_GATEWAY_TYPE: "TCP",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_fail_to_connect(hass: HomeAssistant) -> None:
    """Test configuring a gateway via tcp."""
    step = await get_form(hass, CONF_GATEWAY_TYPE_TCP, "gw_tcp")
    flow_id = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=False
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "2.4",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert "errors" in result
    errors = result["errors"]
    assert errors
    assert errors.get("base") == "cannot_connect"
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    ("gateway_type", "expected_step_id", "user_input", "err_field", "err_string"),
    [
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "a",
            },
            CONF_VERSION,
            "invalid_version",
        ),
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "a.b",
            },
            CONF_VERSION,
            "invalid_version",
        ),
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "4",
            },
            CONF_VERSION,
            "invalid_version",
        ),
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.1",
                CONF_VERSION: "v3",
            },
            CONF_VERSION,
            "invalid_version",
        ),
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "127.0.0.",
                CONF_VERSION: "2.4",
            },
            CONF_DEVICE,
            "invalid_ip",
        ),
        (
            CONF_GATEWAY_TYPE_TCP,
            "gw_tcp",
            {
                CONF_TCP_PORT: 5003,
                CONF_DEVICE: "abcd",
                CONF_VERSION: "2.4",
            },
            CONF_DEVICE,
            "invalid_ip",
        ),
        (
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
        ),
        (
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
        ),
        (
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
        ),
        (
            CONF_GATEWAY_TYPE_MQTT,
            "gw_mqtt",
            {
                CONF_RETAIN: True,
                CONF_TOPIC_IN_PREFIX: "asdf",
                CONF_TOPIC_OUT_PREFIX: "asdf",
                CONF_VERSION: "2.4",
            },
            CONF_TOPIC_OUT_PREFIX,
            "same_topic",
        ),
    ],
)
async def test_config_invalid(
    hass: HomeAssistant,
    mqtt: None,
    gateway_type: ConfGatewayType,
    expected_step_id: str,
    user_input: dict[str, Any],
    err_field: str,
    err_string: str,
) -> None:
    """Perform a test that is expected to generate an error."""
    step = await get_form(hass, gateway_type, expected_step_id)
    flow_id = step["flow_id"]

    with patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.gateway.socket.getaddrinfo",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert "errors" in result
    errors = result["errors"]
    assert errors
    assert err_field in errors
    assert errors[err_field] == err_string
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    ("first_input", "second_input", "expected_result"),
    [
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "same2",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "same2",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={CONF_TOPIC_IN_PREFIX: "duplicate_topic"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "different1",
                CONF_TOPIC_OUT_PREFIX: "different2",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "different3",
                CONF_TOPIC_OUT_PREFIX: "different4",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "different2",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "different4",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={CONF_TOPIC_IN_PREFIX: "duplicate_topic"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "different2",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "different1",
                CONF_TOPIC_OUT_PREFIX: "same1",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={CONF_TOPIC_OUT_PREFIX: "duplicate_topic"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "different2",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_VERSION: "2.3",
                CONF_TOPIC_IN_PREFIX: "same1",
                CONF_TOPIC_OUT_PREFIX: "different1",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={CONF_TOPIC_IN_PREFIX: "duplicate_topic"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "127.0.0.1",
                CONF_PERSISTENCE_FILE: "same.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "same.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={"persistence_file": "duplicate_persistence_file"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "127.0.0.1",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "same.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "127.0.0.1",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "different1.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "different2.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.FORM, errors={"base": "already_configured"}),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "different1.json",
                CONF_TCP_PORT: 343,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_PERSISTENCE_FILE: "different2.json",
                CONF_TCP_PORT: 5003,
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.2",
                CONF_TCP_PORT: 5003,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_TCP,
                CONF_DEVICE: "192.168.1.3",
                CONF_TCP_PORT: 5003,
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "different1.json",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "different2.json",
            },
            FlowResult(type=FlowResultType.FORM, errors={"base": "already_configured"}),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM6",
                CONF_BAUD_RATE: 57600,
                CONF_VERSION: "2.3",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_VERSION: "2.3",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_BAUD_RATE: 115200,
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "different1.json",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_BAUD_RATE: 57600,
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "different2.json",
            },
            FlowResult(type=FlowResultType.FORM, errors={"base": "already_configured"}),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM5",
                CONF_BAUD_RATE: 115200,
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "same.json",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM6",
                CONF_BAUD_RATE: 57600,
                CONF_VERSION: "2.3",
                CONF_PERSISTENCE_FILE: "same.json",
            },
            FlowResult(
                type=FlowResultType.FORM,
                errors={"persistence_file": "duplicate_persistence_file"},
            ),
        ),
        (
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_MQTT,
                CONF_DEVICE: "mqtt",
                CONF_PERSISTENCE_FILE: "bla.json",
                CONF_VERSION: "1.4",
            },
            {
                CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
                CONF_DEVICE: "COM6",
                CONF_PERSISTENCE_FILE: "bla2.json",
                CONF_BAUD_RATE: 115200,
                CONF_VERSION: "1.4",
            },
            FlowResult(type=FlowResultType.CREATE_ENTRY),
        ),
    ],
)
async def test_duplicate(
    hass: HomeAssistant,
    mqtt: None,
    first_input: dict,
    second_input: dict,
    expected_result: FlowResult,
) -> None:
    """Test duplicate detection."""

    with patch("sys.platform", "win32"), patch(
        "homeassistant.components.mysensors.config_flow.try_connect", return_value=True
    ), patch(
        "homeassistant.components.mysensors.async_setup_entry",
        return_value=True,
    ):
        MockConfigEntry(domain=DOMAIN, data=first_input).add_to_hass(hass)

        second_gateway_type = second_input.pop(CONF_GATEWAY_TYPE)
        result = await get_form(
            hass, second_gateway_type, GATEWAY_TYPE_TO_STEP[second_gateway_type]
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            second_input,
        )
        await hass.async_block_till_done()

        for key, val in expected_result.items():
            assert result[key] == val  # type: ignore[literal-required]
