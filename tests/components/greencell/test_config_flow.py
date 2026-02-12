"""Tests for Greencell EVSE config flow."""

from __future__ import annotations

import asyncio
from datetime import datetime
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
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

# Valid Habu Den serial: EVGC021[A-Z][0-9]{8}ZM[0-9]{4}
HABU_DEN_SERIAL = "EVGC021A12345678ZM0001"
HABU_DEN_SERIAL_2 = "EVGC021B87654321ZM0002"
# Invalid serial (not matching Habu Den pattern)
OTHER_DEVICE_SERIAL = "OTHER12345678"

# Short timeout for fast tests
FAST_DISCOVERY_TIMEOUT = 0.2


@pytest.fixture(autouse=True)
def fast_discovery():
    """Patch discovery timeout and grace period sleep for all tests."""
    with (
        patch(
            "homeassistant.components.greencell.const.DISCOVERY_TIMEOUT",
            FAST_DISCOVERY_TIMEOUT,
        ),
        patch(
            "homeassistant.components.greencell.DISCOVERY_TIMEOUT",
            FAST_DISCOVERY_TIMEOUT,
        ),
    ):
        original_sleep = asyncio.sleep

        async def patched_sleep(delay, *args, **kwargs):
            if delay == 0.5:
                return await original_sleep(0)
            return await original_sleep(delay)

        with patch(
            "homeassistant.components.greencell.config_flow.asyncio.sleep",
            side_effect=patched_sleep,
        ):
            yield


async def _init_flow_and_fire_discovery(
    hass: HomeAssistant,
    payloads: list[str],
    delay: float = 0.05,
) -> config_entries.ConfigFlowResult:
    """Initialize flow and fire discovery messages concurrently."""

    async def fire_messages() -> None:
        await asyncio.sleep(delay)
        for payload in payloads:
            async_fire_mqtt_message(hass, GREENCELL_DISC_TOPIC, payload)

    fire_task = hass.async_create_task(fire_messages())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await fire_task
    await hass.async_block_till_done()

    return result


async def test_user_setup_single_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup with single device triggers selections."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{HABU_DEN_SERIAL}"}}'],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_multiple_devices(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test user setup with multiple devices triggers selection."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [
            f'{{"id": "{HABU_DEN_SERIAL}"}}',
            f'{{"id": "{HABU_DEN_SERIAL_2}"}}',
            f'{{"id": "{OTHER_DEVICE_SERIAL}"}}',
        ],
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"serial_number": HABU_DEN_SERIAL_2}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {HABU_DEN_SERIAL_2}"
    assert result["data"] == {"serial_number": HABU_DEN_SERIAL_2}


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
) -> None:
    """Test that configuring same device twice aborts."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{HABU_DEN_SERIAL}"}}'],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{HABU_DEN_SERIAL}"}}'],
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
        True,
    )


async def test_select_step_shows_all_discovered_devices(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test select step displays all discovered devices."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [
            f'{{"id": "{HABU_DEN_SERIAL}"}}',
            f'{{"id": "{HABU_DEN_SERIAL_2}"}}',
        ],
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    schema = result["data_schema"].schema
    serial_field = schema["serial_number"]
    assert HABU_DEN_SERIAL in serial_field.container
    assert HABU_DEN_SERIAL_2 in serial_field.container


def _mqtt_service_info(payload: str) -> MqttServiceInfo:
    """Create a MqttServiceInfo for testing."""
    return MqttServiceInfo(
        topic="greencell/broadcast/device",
        payload=payload,
        qos=0,
        retain=False,
        subscribed_topic="greencell/broadcast/device",
        timestamp=datetime.now(),
    )


async def test_mqtt_discovery_creates_confirm_step(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_service_info,
) -> None:
    """Test MQTT discovery triggers confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=mqtt_service_info(f'{{"id": "{HABU_DEN_SERIAL}"}}'),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_mqtt_discovery_confirm_creates_entry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test confirming MQTT discovery creates config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=_mqtt_service_info(f'{{"id": "{HABU_DEN_SERIAL}"}}'),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {HABU_DEN_SERIAL}"
    assert result["data"] == {"serial_number": HABU_DEN_SERIAL}


async def test_mqtt_discovery_other_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test MQTT discovery with non-HabuDen device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=_mqtt_service_info(f'{{"id": "{OTHER_DEVICE_SERIAL}"}}'),
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
) -> None:
    """Test MQTT discovery aborts for already configured device."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=HABU_DEN_SERIAL,
        data={"serial_number": HABU_DEN_SERIAL},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=_mqtt_service_info(f'{{"id": "{HABU_DEN_SERIAL}"}}'),
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
    payload: str,
) -> None:
    """Test MQTT discovery aborts on invalid payloads."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=_mqtt_service_info(payload),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"
