"""Tests for Greencell EVSE config flow."""

from __future__ import annotations

import asyncio
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

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient

# Valid Habu Den serial: EVGC021[A-Z][0-9]{8}ZM[0-9]{4}
HABU_DEN_SERIAL = "EVGC021A12345678ZM0001"
HABU_DEN_SERIAL_2 = "EVGC021B87654321ZM0002"
# Invalid serial (not matching Habu Den pattern)
OTHER_DEVICE_SERIAL = "OTHER12345678"

# Short timeout for fast tests
FAST_DISCOVERY_TIMEOUT = 0.1

# Patch target - where the constant is used, not where it's defined
DISCOVERY_TIMEOUT_PATCH = (
    "homeassistant.components.greencell.config_flow.DISCOVERY_TIMEOUT"
)


@pytest.fixture(autouse=True)
def fast_discovery():
    """Patch discovery timeout for all tests."""
    with patch(DISCOVERY_TIMEOUT_PATCH, FAST_DISCOVERY_TIMEOUT):
        yield


async def _init_flow_and_fire_discovery(
    hass: HomeAssistant,
    payloads: list[str],
    delay: float = 0.02,
) -> config_entries.ConfigFlowResult:
    """Initialize flow and fire discovery messages concurrently."""

    async def fire_messages() -> None:
        """Fire MQTT messages after a short delay."""
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
    """Test user setup with single device discovery."""
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{HABU_DEN_SERIAL}"}}'],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{GREENCELL_HABU_DEN} {HABU_DEN_SERIAL}"
    assert result["data"] == {"serial_number": HABU_DEN_SERIAL}


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
    # First configuration
    result = await _init_flow_and_fire_discovery(
        hass,
        [f'{{"id": "{HABU_DEN_SERIAL}"}}'],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second configuration attempt
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
        # Valid Habu Den serials (pattern: EVGC021[A-Z][0-9]{8}ZM[0-9]{4})
        ("EVGC021A12345678ZM0001", GREENCELL_HABU_DEN),
        ("EVGC021Z99999999ZM9999", GREENCELL_HABU_DEN),
        # Invalid serials - should be classified as other device
        ("OTHER12345678", GREENCELL_OTHER_DEVICE),
        ("EVGC021a12345678ZM0001", GREENCELL_OTHER_DEVICE),  # lowercase letter
        ("EVGC021A1234567ZM0001", GREENCELL_OTHER_DEVICE),  # too few digits
        ("EVGC022A12345678ZM0001", GREENCELL_OTHER_DEVICE),  # wrong prefix
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
