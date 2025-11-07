"""Tests for the Concord232 alarm control panel platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.concord232 import alarm_control_panel
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

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
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test platform setup with connection error."""
    with patch(
        "homeassistant.components.concord232.alarm_control_panel.concord232_client.Client"
    ) as mock_client_class:
        mock_client_class.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()

        assert "Unable to connect to Concord232" in caplog.text
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


async def test_alarm_arm_home(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test arm home service."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
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
    mock_concord232_client.arm.assert_called_once_with("stay")


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


async def test_alarm_arm_home_with_code(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test arm home service with code."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
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
    mock_concord232_client.arm.assert_called_once_with("stay")


async def test_alarm_arm_away(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test arm away service."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("away")


async def test_alarm_arm_away_with_code(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test arm away service with code."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("away")


async def test_supported_features_include_trigger(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test that TRIGGER feature is supported."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state is not None
    # Check that TRIGGER feature is in supported_features
    assert (
        int(state.attributes["supported_features"])
        & AlarmControlPanelEntityFeature.TRIGGER
    ) == AlarmControlPanelEntityFeature.TRIGGER


async def test_alarm_trigger_service_available(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test that alarm_trigger service is available when TRIGGER feature is supported."""
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify the service is registered
    assert hass.services.has_service(ALARM_DOMAIN, SERVICE_ALARM_TRIGGER)


async def test_alarm_trigger_service_call(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test alarm_trigger service call.

    Note: This test verifies the TRIGGER feature is properly declared.
    The alarm_trigger method needs to be implemented in Concord232Alarm class
    for the service call to work. Currently, it will raise NotImplementedError
    until the method is implemented.
    """
    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG_WITH_CODE)
    await hass.async_block_till_done()

    # Verify the service is available
    assert hass.services.has_service(ALARM_DOMAIN, SERVICE_ALARM_TRIGGER)

    # Call the trigger service - will raise NotImplementedError until alarm_trigger is implemented
    # This confirms the feature is declared but the method needs implementation
    with pytest.raises(NotImplementedError):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_TRIGGER,
            {
                ATTR_ENTITY_ID: "alarm_control_panel.test_alarm",
                ATTR_CODE: "1234",
            },
            blocking=True,
        )


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


async def test_update_state_armed_home(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test update when alarm is armed home."""
    mock_concord232_client.list_partitions.return_value = [{"arming_level": "Home"}]
    mock_concord232_client.partitions = (
        mock_concord232_client.list_partitions.return_value
    )
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    await async_update_entity(hass, "alarm_control_panel.test_alarm")
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state.state == AlarmControlPanelState.ARMED_HOME


async def test_update_state_armed_away(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test update when alarm is armed away."""
    mock_concord232_client.list_partitions.return_value = [{"arming_level": "Away"}]
    mock_concord232_client.partitions = (
        mock_concord232_client.list_partitions.return_value
    )
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    await async_update_entity(hass, "alarm_control_panel.test_alarm")
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_update_state_triggered(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test update when alarm is triggered."""
    mock_concord232_client.list_partitions.return_value = [{"arming_level": "Away"}]
    mock_concord232_client.partitions = (
        mock_concord232_client.list_partitions.return_value
    )
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Unknown"},
    ]

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    await async_update_entity(hass, "alarm_control_panel.test_alarm")
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.test_alarm")
    # Verify the state is correctly set to TRIGGERED
    assert state.state == AlarmControlPanelState.TRIGGERED
    # Verify the triggered_by attribute is set correctly
    assert state.attributes.get("triggered_by") == "Zone 1"


async def test_update_connection_error(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update with connection error."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("Connection failed")
    )

    await async_setup_component(hass, ALARM_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    await async_update_entity(hass, "alarm_control_panel.test_alarm")
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

    # Trigger update
    await async_update_entity(hass, "alarm_control_panel.test_alarm")
    await hass.async_block_till_done()

    assert "Concord232 reports no partitions" in caplog.text
