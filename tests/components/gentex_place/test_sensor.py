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
    # Remove the shadow to simulate a missing device
    del coordinator.shadows["thing-001"]

    # Trigger a state write
    coordinator._async_notify_listeners()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.master_bedroom_co_alarm")
    assert state.state == "unknown"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_sensor_all_alarm_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that all AlarmStatus values are correctly represented."""
    await setup_integration(hass, mock_config_entry)

    states = {
        0: "idle",
        1: "test",
        2: "pre_alarm",
        3: "alarm",
        4: "critical_alarm",
        5: "hushed",
        6: "not_present",
    }

    for value, expected in states.items():
        payload = json.dumps({"state": {"reported": {"coAlarmStatus": value}}}).encode()
        trigger_shadow_callback(
            mock_mqtt_client,
            "$aws/things/thing-001/shadow/update/accepted",
            payload,
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.master_bedroom_co_alarm")
        assert state.state == expected, (
            f"Expected {expected} for value {value}, got {state.state}"
        )
