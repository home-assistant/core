"""Tests for the Concord232 alarm control panel platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_CODE,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

VALID_CONFIG = {
    ALARM_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
        CONF_NAME: "Test Alarm",
    }
}

VALID_CONFIG_WITH_CODE = {
    ALARM_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
        CONF_NAME: "Test Alarm",
        CONF_CODE: "1234",
    }
}

VALID_CONFIG_SILENT_MODE = {
    ALARM_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
        CONF_NAME: "Test Alarm",
        CONF_MODE: "silent",
    }
}


async def test_setup_platform(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test platform setup."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED


async def test_setup_platform_connection_error(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test platform setup with connection error."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("Connection failed")
    )

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.test_alarm") is None


async def test_alarm_disarm(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test disarm service."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.test_alarm"},
        blocking=True,
    )
    mock_concord232_client.disarm.assert_called_once_with(None)


async def test_alarm_disarm_with_code(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test disarm service with code."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )
    mock_concord232_client.disarm.assert_called_once_with("1234")


async def test_alarm_disarm_invalid_code(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test disarm service with invalid code."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "9999",
        },
        blocking=True,
    )
    mock_concord232_client.disarm.assert_not_called()
    assert "Invalid code given" in caplog.text


@pytest.mark.parametrize(
    ("service", "expected_arm_call"),
    [
        (SERVICE_ALARM_ARM_HOME, "stay"),
        (SERVICE_ALARM_ARM_AWAY, "away"),
    ],
)
async def test_alarm_arm(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    service: str,
    expected_arm_call: str,
) -> None:
    """Test arm service."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with(expected_arm_call)


async def test_alarm_arm_home_silent_mode(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test arm home service with silent mode."""
    config_with_code = VALID_CONFIG_SILENT_MODE.copy()
    config_with_code[ALARM_DOMAIN][CONF_CODE] = "1234"
    await async_setup_component(hass, ALARM_DOMAIN, config_with_code)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("stay", "silent")


async def test_update_state_disarmed(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test update when alarm is disarmed."""
    mock_concord232_client.list_partitions.return_value = [{"arming_level": "Off"}]
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state.state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(
    ("arming_level", "expected_state"),
    [
        ("Home", AlarmControlPanelState.ARMED_HOME),
        ("Away", AlarmControlPanelState.ARMED_AWAY),
    ],
)
async def test_update_state_armed(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    arming_level: str,
    expected_state: str,
) -> None:
    """Test update when alarm is armed."""
    mock_concord232_client.list_partitions.return_value = [
        {"arming_level": arming_level}
    ]
    mock_concord232_client.partitions = (
        mock_concord232_client.list_partitions.return_value
    )
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state.state == expected_state


async def test_update_connection_error(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update with connection error."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("Connection failed")
    )

    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Unable to connect to" in caplog.text


async def test_update_no_partitions(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update when no partitions are available."""
    mock_concord232_client.list_partitions.return_value = []

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    assert "Concord232 reports no partitions" in caplog.text
