"""Test the Ness Alarm control panel."""

from unittest.mock import AsyncMock, patch

from nessclient import ArmingMode, ArmingState
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.ness_alarm import (
    CONF_SUPPORT_HOME_ARM,
    SIGNAL_ARMING_STATE_CHANGED,
)
from homeassistant.components.ness_alarm.const import DOMAIN
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    SERVICE_ALARM_DISARM,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
        },
    )


@pytest.fixture
def mock_client():
    """Create a mock Ness client."""
    client = AsyncMock()
    client.disarm = AsyncMock()
    client.arm_away = AsyncMock()
    client.arm_home = AsyncMock()
    client.panic = AsyncMock()
    client.keepalive = AsyncMock()
    client.update = AsyncMock()
    client.close = AsyncMock()
    return client


async def test_alarm_control_panel_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test alarm control panel setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None
    assert state.name == "Alarm Panel"


async def test_alarm_control_panel_disarm(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test disarm."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    mock_client.disarm.assert_called_once_with("1234")


async def test_alarm_control_panel_unhandled_arming_state(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test handling of unknown/unhandled arming states."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the alarm panel entity
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None

    # Create a mock unhandled arming state (assuming there might be future states)
    # We'll use a mock value that doesn't match any of the handled cases
    unhandled_state = "SOME_FUTURE_STATE"

    # Mock the enum to have our test value and check that warning is logged
    with (
        patch.object(ArmingState, "__new__", return_value=unhandled_state),
        patch(
            "homeassistant.components.ness_alarm.alarm_control_panel._LOGGER.warning"
        ) as mock_warning,
    ):
        async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, unhandled_state, None)
        await hass.async_block_till_done()

        mock_warning.assert_called_once_with(
            "Unhandled arming state: %s", unhandled_state
        )


async def test_alarm_control_panel_arm_away(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test arm away."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    mock_client.arm_away.assert_called_once_with("1234")


async def test_alarm_control_panel_arm_home(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test arm home."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_home",
        {
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    mock_client.arm_home.assert_called_once_with("1234")


async def test_alarm_control_panel_trigger(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test trigger (panic)."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_trigger",
        {
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
        },
        blocking=True,
    )

    mock_client.panic.assert_called_once_with(None)


async def test_alarm_control_panel_no_home_arm_support(
    hass: HomeAssistant,
    mock_client,
) -> None:
    """Test alarm panel without home arm support."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
        },
        options={
            CONF_SUPPORT_HOME_ARM: False,  # Disable home arm support
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None

    assert (
        not state.attributes.get("supported_features", 0)
        & AlarmControlPanelEntityFeature.ARM_HOME
    )

    # Try to arm home when not supported - should raise ServiceNotSupported
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            ALARM_DOMAIN,
            "alarm_arm_home",
            {
                ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
                ATTR_CODE: "1234",
            },
            blocking=True,
        )

    # The client method should not have been called
    mock_client.arm_home.assert_not_called()


async def test_alarm_control_panel_all_arming_states(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test all arming state transitions."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test UNKNOWN state
    async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.UNKNOWN, None)
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == "unknown"

    # Test DISARMED state
    async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.DISARMED, None)
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.DISARMED

    # Test ARMING state
    async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMING, None)
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMING

    # Test EXIT_DELAY state
    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.EXIT_DELAY, None
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMING

    # Test ARMED with different modes
    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMED, ArmingMode.ARMED_AWAY
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMED, ArmingMode.ARMED_HOME
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMED_HOME

    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMED, ArmingMode.ARMED_NIGHT
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMED_NIGHT

    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMED, ArmingMode.ARMED_VACATION
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMED_VACATION

    # Test ARMED with unmapped mode (ARMED_DAY, ARMED_HIGHEST)
    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ARMED, ArmingMode.ARMED_DAY
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    # Test ENTRY_DELAY state
    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.ENTRY_DELAY, None
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.PENDING

    # Test TRIGGERED state
    async_dispatcher_send(
        hass, SIGNAL_ARMING_STATE_CHANGED, ArmingState.TRIGGERED, None
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state.state == AlarmControlPanelState.TRIGGERED
