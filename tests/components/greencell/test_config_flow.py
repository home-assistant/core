"""Tests for Greencell EVSE config flow."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.greencell.const import (
    DOMAIN,
    GREENCELL_BROADCAST_TOPIC,
    GREENCELL_DISC_TOPIC,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
)
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_SERIAL_NUMBER, TEST_SERIAL_NUMBER_2

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

OTHER_DEVICE_SERIAL = "OTHER12345678"


@pytest.fixture(autouse=True)
def fast_discovery():
    """Patch discovery timeout and grace period to 0 for all tests."""
    with (
        patch(
            "homeassistant.components.greencell.const.DISCOVERY_TIMEOUT",
            0.01,
        ),
        patch(
            "homeassistant.components.greencell.DISCOVERY_TIMEOUT",
            0.01,
        ),
        patch(
            "homeassistant.components.greencell.config_flow.asyncio.sleep",
            return_value=None,
        ),
    ):
        yield


async def _init_flow_and_fire_discovery(
    hass: HomeAssistant,
    payloads: list[str],
) -> config_entries.ConfigFlowResult:
    """Initialize user flow and fire discovery messages synchronously."""

    async def _mock_subscribe(hass_arg, topic, msg_callback, *args, **kwargs):
        """Fire payloads immediately when subscription happens."""
        for payload in payloads:
            msg_callback(
                ReceiveMessage(
                    topic=GREENCELL_DISC_TOPIC,
                    payload=payload,
                    qos=0,
                    retain=False,
                    subscribed_topic=GREENCELL_DISC_TOPIC,
                    timestamp=time.time(),
                )
            )
        return lambda: None

    with patch(
        "homeassistant.components.greencell.config_flow.mqtt.async_subscribe",
        side_effect=_mock_subscribe,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    return result


async def test_user_setup_single_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup with single device creates entry."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{TEST_SERIAL_NUMBER}"}}'],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}"
    assert result["data"] == {"serial_number": TEST_SERIAL_NUMBER}
    assert result["result"].unique_id == TEST_SERIAL_NUMBER


async def test_user_setup_multiple_devices(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup with multiple devices triggers selection."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [
            f'{{"id": "{TEST_SERIAL_NUMBER}"}}',
            f'{{"id": "{TEST_SERIAL_NUMBER_2}"}}',
            f'{{"id": "{OTHER_DEVICE_SERIAL}"}}',
        ],
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"serial_number": TEST_SERIAL_NUMBER_2}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER_2}"
    assert result["data"] == {"serial_number": TEST_SERIAL_NUMBER_2}
    assert result["result"].unique_id == TEST_SERIAL_NUMBER_2


async def test_user_setup_no_devices(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup aborts when no devices respond."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_discovery_data"


async def test_user_setup_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test user setup aborts when MQTT is not configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"


async def test_user_setup_mqtt_not_connected(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup aborts when MQTT is not connected."""
    with patch(
        "homeassistant.components.greencell.config_flow.mqtt.is_connected",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_connected"


async def test_duplicate_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that configuring same device twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{TEST_SERIAL_NUMBER}"}}'],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{BAD JSON}",
        '{"name": "device"}',
        '{"id": ""}',
        '{"id": "   "}',
        '{"id": 12345}',
    ],
    ids=[
        "empty_payload",
        "bad_json",
        "missing_id",
        "empty_id",
        "whitespace_id",
        "non_string_id",
    ],
)
async def test_invalid_discovery_payload(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    payload: str,
) -> None:
    """Test that invalid discovery payloads are ignored."""
    result = await _init_flow_and_fire_discovery(hass, [payload])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_discovery_data"


@pytest.mark.parametrize(
    ("serial", "expected_name"),
    [
        ("EVGC021A12345678ZM0001", GREENCELL_HABU_DEN),
        ("EVGC021Z99999999ZM9999", GREENCELL_HABU_DEN),
        ("OTHER12345678", GREENCELL_OTHER_DEVICE),
        ("EVGC021a12345678ZM0001", GREENCELL_OTHER_DEVICE),
        ("EVGC021A1234567ZM0001", GREENCELL_OTHER_DEVICE),
        ("EVGC022A12345678ZM0001", GREENCELL_OTHER_DEVICE),
    ],
    ids=[
        "habu_den_valid_1",
        "habu_den_valid_2",
        "other_device",
        "habu_den_lowercase_invalid",
        "habu_den_short_digits",
        "habu_den_wrong_prefix",
    ],
)
async def test_device_naming(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    serial: str,
    expected_name: str,
) -> None:
    """Test device name is determined correctly from serial prefix."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{serial}"}}'],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{expected_name} {serial}"


async def test_broadcast_message_published(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that discovery broadcast is published on flow init."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_called_with(
        GREENCELL_BROADCAST_TOPIC,
        '{"name": "BROADCAST"}',
        0,
        False,
    )


async def test_select_step_shows_all_discovered_devices(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test select step displays all discovered devices."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [
            f'{{"id": "{TEST_SERIAL_NUMBER}"}}',
            f'{{"id": "{TEST_SERIAL_NUMBER_2}"}}',
        ],
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    schema = result["data_schema"].schema
    serial_field = schema["serial_number"]
    assert TEST_SERIAL_NUMBER in serial_field.container
    assert TEST_SERIAL_NUMBER_2 in serial_field.container


async def test_mqtt_discovery_confirm_creates_entry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery triggers confirm step and creates entry on confirm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{TEST_SERIAL_NUMBER}"}}'),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {TEST_SERIAL_NUMBER}"
    assert result["data"] == {"serial_number": TEST_SERIAL_NUMBER}
    assert result["result"].unique_id == TEST_SERIAL_NUMBER


async def test_mqtt_discovery_other_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery with non-HabuDen device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{OTHER_DEVICE_SERIAL}"}}'),
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_OTHER_DEVICE} {OTHER_DEVICE_SERIAL}"


async def test_mqtt_discovery_duplicate_aborts(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery aborts for already configured device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{TEST_SERIAL_NUMBER}"}}'),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "payload",
    [
        "{BAD JSON}",
        '{"name": "device"}',
        '{"id": ""}',
        '{"id": "   "}',
        '{"id": 12345}',
    ],
    ids=[
        "bad_json",
        "missing_id",
        "empty_id",
        "whitespace_id",
        "non_string_id",
    ],
)
async def test_mqtt_discovery_invalid_payload(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
    payload: str,
) -> None:
    """Test MQTT discovery aborts on invalid payloads."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(payload),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_data"


async def test_mqtt_discovery_attribute_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery aborts when json.loads raises AttributeError."""
    with patch(
        "homeassistant.components.greencell.config_flow.json.loads",
        side_effect=AttributeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_MQTT},
            data=mqtt_service_info('{"id": "anything"}'),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_data"


async def test_user_setup_mqtt_subscription_value_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup aborts when MQTT subscription raises ValueError."""
    with patch(
        "homeassistant.components.greencell.config_flow.mqtt.async_subscribe",
        side_effect=ValueError("bad topic"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_subscription_failed"


async def test_mqtt_discovery_already_in_progress(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery aborts when another flow for same serial is in progress."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{TEST_SERIAL_NUMBER}"}}'),
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{TEST_SERIAL_NUMBER}"}}'),
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"
