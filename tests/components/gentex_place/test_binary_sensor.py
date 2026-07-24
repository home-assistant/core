"""Tests for the Place binary sensor platform."""

import json
from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration, trigger_shadow_callback

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_binary_sensor_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that alarm binary sensor entities are created for each device."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.master_bedroom_smoke") is not None
    assert hass.states.get("binary_sensor.master_bedroom_carbon_monoxide") is not None
    assert hass.states.get("binary_sensor.master_bedroom_heat") is not None


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, STATE_OFF, id="idle"),
        pytest.param(1, STATE_OFF, id="test"),
        pytest.param(2, STATE_OFF, id="pre_alarm"),
        pytest.param(3, STATE_ON, id="alarm"),
        pytest.param(4, STATE_ON, id="critical_alarm"),
        pytest.param(5, STATE_OFF, id="hushed"),
        pytest.param(6, STATE_UNAVAILABLE, id="not_present"),
    ],
)
async def test_binary_sensor_alarm_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test each AlarmStatus maps to the expected binary sensor state."""
    await setup_integration(hass, mock_config_entry)

    payload = json.dumps(
        {"state": {"reported": {"smokeAlarmStatus": raw_value}}}
    ).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.master_bedroom_smoke").state == expected_state
