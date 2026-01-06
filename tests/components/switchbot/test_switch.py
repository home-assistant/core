"""Test the switchbot switches."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot.devices.device import SwitchbotOperationError

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from . import (
    PLUG_MINI_EU_SERVICE_INFO,
    RELAY_SWITCH_1_SERVICE_INFO,
    RELAY_SWITCH_2PM_SERVICE_INFO,
    WOHAND_SERVICE_INFO,
    WORELAY_SWITCH_1PM_SERVICE_INFO,
)

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_switchbot_switch_with_restore_state(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Switchbot Switch restores state correctly after reboot."""
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bot")
    entity_id = "switch.test_name"

    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_ON,
                {"last_run_success": True},
            )
        ],
    )

    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.switch.switchbot.Switchbot.switch_mode",
        return_value=False,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes["last_run_success"] is True


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_TURN_ON, "turn_on"),
        (SERVICE_TURN_OFF, "turn_off"),
    ],
)
async def test_exception_handling_switch(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for switch service with exception."""
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bot")
    entry.add_to_hass(hass)
    entity_id = "switch.test_name"

    patch_target = (
        f"homeassistant.components.switchbot.switch.switchbot.Switchbot.{mock_method}"
    )

    with patch(patch_target, new=AsyncMock(side_effect=exception)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [
        ("plug_mini_eu", PLUG_MINI_EU_SERVICE_INFO),
        ("relay_switch_1", RELAY_SWITCH_1_SERVICE_INFO),
        ("relay_switch_1pm", WORELAY_SWITCH_1PM_SERVICE_INFO),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_TURN_ON, "turn_on"),
        (SERVICE_TURN_OFF, "turn_off"),
    ],
)
async def test_relay_switch_control(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    service: str,
    mock_method: str,
) -> None:
    """Test Relay Switch control."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.switch.switchbot.SwitchbotRelaySwitch",
        update=AsyncMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "switch.test_name"

        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
async def test_relay_switch_2pm_control(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service: str,
    mock_method: str,
) -> None:
    """Test Relay Switch 2PM control."""
    inject_bluetooth_service_info(hass, RELAY_SWITCH_2PM_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="relay_switch_2pm")
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.switch.switchbot.SwitchbotRelaySwitch2PM",
        update=AsyncMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id_1 = "switch.test_name_channel_1"

        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id_1},
            blocking=True,
        )

        mocked_instance.assert_called_with(1)

        entity_id_2 = "switch.test_name_channel_2"

        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id_2},
            blocking=True,
        )

        mocked_instance.assert_called_with(2)


@pytest.mark.parametrize(
    ("sensor_type", "service_info", "entity_id", "mock_class"),
    [
        (
            "relay_switch_1",
            RELAY_SWITCH_1_SERVICE_INFO,
            "switch.test_name",
            "SwitchbotRelaySwitch",
        ),
        (
            "relay_switch_1pm",
            WORELAY_SWITCH_1PM_SERVICE_INFO,
            "switch.test_name",
            "SwitchbotRelaySwitch",
        ),
        (
            "plug_mini_eu",
            PLUG_MINI_EU_SERVICE_INFO,
            "switch.test_name",
            "SwitchbotRelaySwitch",
        ),
        (
            "relay_switch_2pm",
            RELAY_SWITCH_2PM_SERVICE_INFO,
            "switch.test_name_channel_1",
            "SwitchbotRelaySwitch2PM",
        ),
        (
            "relay_switch_2pm",
            RELAY_SWITCH_2PM_SERVICE_INFO,
            "switch.test_name_channel_2",
            "SwitchbotRelaySwitch2PM",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_TURN_ON, "turn_on"),
        (SERVICE_TURN_OFF, "turn_off"),
    ],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
async def test_relay_switch_control_with_exception(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    entity_id: str,
    mock_class: str,
    service: str,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test Relay Switch control with exception."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    with patch.multiple(
        f"homeassistant.components.switchbot.switch.switchbot.{mock_class}",
        update=AsyncMock(return_value=None),
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
