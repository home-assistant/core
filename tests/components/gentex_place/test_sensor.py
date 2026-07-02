"""Tests for the Place sensor platform."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant

from . import setup_integration, trigger_shadow_callback

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_sensor_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that alarm sensor entities are created for each device."""
    await setup_integration(hass, mock_config_entry)

    co = hass.states.get("sensor.master_bedroom_co_alarm")
    heat = hass.states.get("sensor.master_bedroom_heat_alarm")
    smoke = hass.states.get("sensor.master_bedroom_smoke_alarm")

    assert co is not None
    assert heat is not None
    assert smoke is not None


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_sensor_initial_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test sensor values reflect initial shadow state from discovery."""
    await setup_integration(hass, mock_config_entry)

    co = hass.states.get("sensor.master_bedroom_co_alarm")
    heat = hass.states.get("sensor.master_bedroom_heat_alarm")
    smoke = hass.states.get("sensor.master_bedroom_smoke_alarm")

    assert co.state == "idle"
    assert heat.state == "idle"
    assert smoke.state == "idle"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_sensor_updates_on_shadow_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test sensor values update when an MQTT shadow message arrives."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.master_bedroom_co_alarm").state == "idle"

    payload = json.dumps(
        {"state": {"reported": {"coAlarmStatus": 3, "smokeAlarmStatus": 5}}}
    ).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.master_bedroom_co_alarm").state == "alarm"
    assert hass.states.get("sensor.master_bedroom_smoke_alarm").state == "hushed"
    # Heat unchanged
    assert hass.states.get("sensor.master_bedroom_heat_alarm").state == "idle"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_sensor_unknown_device_returns_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that a sensor returns unknown when its shadow is missing."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    # Simulate the device disappearing from coordinator data
    coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.master_bedroom_co_alarm")
    assert state.state == "unknown"


@pytest.mark.usefixtures("aioclient_mock_fixture")
@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, "idle", id="idle"),
        pytest.param(1, "test", id="test"),
        pytest.param(2, "pre_alarm", id="pre_alarm"),
        pytest.param(3, "alarm", id="alarm"),
        pytest.param(4, "critical_alarm", id="critical_alarm"),
        pytest.param(5, "hushed", id="hushed"),
        pytest.param(6, "not_present", id="not_present"),
        pytest.param(None, "not_present", id="null_value"),
        pytest.param(99, "not_present", id="out_of_range_value"),
    ],
)
async def test_sensor_all_alarm_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test that each AlarmStatus value maps to the expected sensor state."""
    await setup_integration(hass, mock_config_entry)

    payload = json.dumps({"state": {"reported": {"coAlarmStatus": raw_value}}}).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.master_bedroom_co_alarm")
    assert state.state == expected_state
