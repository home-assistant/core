"""Tests for the Concord232 alarm control panel platform."""

from datetime import timedelta
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
from homeassistant.components.concord232.alarm_control_panel import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_CODE,
    CONF_MODE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "alarm_control_panel.localhost"


@pytest.mark.parametrize(
    ("arming_level", "expected"),
    [
        ("Off", AlarmControlPanelState.DISARMED),
        ("Stay/Home", AlarmControlPanelState.ARMED_HOME),
        ("Away", AlarmControlPanelState.ARMED_AWAY),
    ],
)
async def test_alarm_state(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    arming_level: str,
    expected: AlarmControlPanelState,
) -> None:
    """Test the panel state maps from the partition arming level."""
    mock_concord232_client.list_partitions.return_value = [
        {"arming_level": arming_level}
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


async def test_state_updates_on_poll(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the panel state follows the polled partition state."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED

    mock_concord232_client.list_partitions.return_value = [{"arming_level": "Away"}]
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY


async def test_connection_error_keeps_last_state(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the panel keeps its last state when the server stops answering."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED

    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED
    assert "Unable to connect to" in caplog.text


@pytest.mark.parametrize(
    ("service", "expected_args"),
    [
        (SERVICE_ALARM_ARM_HOME, ("stay",)),
        (SERVICE_ALARM_ARM_AWAY, ("away",)),
    ],
)
async def test_arm_services(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_args: tuple[str, ...],
) -> None:
    """Test arming without a configured code."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with(*expected_args)


async def test_arm_home_silent_mode(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the silent option is passed through when arming home."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MODE: "silent"}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("stay", "silent")


async def test_disarm(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disarming passes the code to the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: "1234"},
        blocking=True,
    )
    mock_concord232_client.disarm.assert_called_once_with("1234")


@pytest.mark.parametrize(
    ("service", "client_method"),
    [
        (SERVICE_ALARM_ARM_HOME, "arm"),
        (SERVICE_ALARM_ARM_AWAY, "arm"),
        (SERVICE_ALARM_DISARM, "disarm"),
    ],
)
@pytest.mark.parametrize(
    ("code", "command_sent"),
    [
        ("1234", True),
        ("9999", False),
    ],
)
async def test_code_validation(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    client_method: str,
    code: str,
    command_sent: bool,
) -> None:
    """Test a configured code gates every command."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CODE: "1234"}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: code},
        blocking=True,
    )
    assert getattr(mock_concord232_client, client_method).called is command_sent


async def test_no_partitions_reports_unknown(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the panel state is unknown when the server reports no partitions."""
    mock_concord232_client.list_partitions.return_value = []
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_setup_connection_error_creates_no_entity(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a connection error during setup leaves no panel entity."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None
    assert "Unable to connect to Concord232" in caplog.text
