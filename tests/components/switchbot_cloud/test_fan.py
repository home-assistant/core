"""Test for the Switchbot Battery Circulator Fan."""

from unittest.mock import patch

from switchbot_api import (
    BatteryCirculatorFanCommands,
    BatteryCirculatorFanMode,
    CommonCommands,
    Device,
    SwitchBotAPI,
)

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_fan_turn_on_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_3(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_4(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "baby", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_5(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_6(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "50"},
        {"power": "on", "mode": "direct", "fanSpeed": "30"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_on_7(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "50"},
        {"power": "on", "mode": "direct"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_not_called()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_turn_off_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_send_command.assert_called_once_with(
            "battery-fan-id-1", CommonCommands.OFF, "command", "default"
        )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_fan_turn_off_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "baby", "fanSpeed": "0"},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_send_command.assert_called_once_with(
            "battery-fan-id-1", CommonCommands.OFF, "command", "default"
        )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_fan_turn_off_3(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "baby", "fanSpeed": "0"},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_send_command.assert_not_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_fan_turn_off_4(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "baby", "fanSpeed": "0"},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_send_command.assert_not_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_fan_set_percentage_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan speed percentage."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        )
    ]

    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "3"},
        {"power": "off", "mode": "direct", "fanSpeed": "5"},
        {"power": "on", "mode": "baby", "fanSpeed": "3"},
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_PERCENTAGE) == 3

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 5},
            blocking=True,
        )
        mock_send_command.assert_not_called()
        # mock_send_command.assert_called_once_with(
        #     "battery-fan-id-1",
        #     BatteryCirculatorFanCommands.SET_WIND_SPEED,
        #     "command",
        #     "5",
        # )
    state = hass.states.get(entity_id)
    assert state.attributes.get("percentage") == 0
    assert state.attributes.get("preset_mode") == BatteryCirculatorFanMode.DIRECT.value


async def test_fan_set_percentage_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan speed percentage."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        )
    ]

    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "3"},
        {"power": "on", "mode": "direct", "fanSpeed": "5"},
        {"power": "on", "mode": "direct", "fanSpeed": "3"},
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_PERCENTAGE) == 3

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 5},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "battery-fan-id-1",
            BatteryCirculatorFanCommands.SET_WIND_SPEED,
            "command",
            "5",
        )
    state = hass.states.get(entity_id)
    assert state.attributes.get("percentage") == 5
    assert state.attributes.get("preset_mode") == BatteryCirculatorFanMode.DIRECT.value


async def test_fan_set_percentage_3(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan speed percentage."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        )
    ]

    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "3"},
        {"power": "on", "mode": "baby", "fanSpeed": "5"},
        {"power": "on", "mode": "baby", "fanSpeed": "3"},
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_PERCENTAGE) == 3

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 5},
            blocking=True,
        )
        mock_send_command.assert_not_called()
    state = hass.states.get(entity_id)
    assert state.attributes.get("percentage") == 0
    assert state.attributes.get("preset_mode") == BatteryCirculatorFanMode.BABY.value


async def test_fan_set_preset_mode_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan preset mode."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        )
    ]

    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "3"},
        {"power": "on", "mode": "natural", "fanSpeed": "0"},
        # {"power": "on", "mode": "direct", "fanSpeed": "10"},
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)
    assert (
        state.attributes.get(ATTR_PRESET_MODE) == BatteryCirculatorFanMode.DIRECT.value
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_PRESET_MODE: BatteryCirculatorFanMode.NATURAL.value,
            },
            blocking=True,
        )
        mock_send_command.assert_awaited_once()
    state = hass.states.get(entity_id)
    assert (
        state.attributes.get(ATTR_PRESET_MODE) == BatteryCirculatorFanMode.NATURAL.value
    )
    assert state.attributes.get(ATTR_PERCENTAGE) == 0


async def test_fan_set_preset_mode_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan preset mode."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="battery-fan-id-1",
            deviceName="battery-fan-1",
            deviceType="Battery Circulator Fan",
            hubDeviceId="test-hub-id",
        )
    ]

    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "3"},
        {"power": "on", "mode": "direct", "fanSpeed": "10"},
        # {"power": "on", "mode": "direct", "fanSpeed": "10"},
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)
    assert (
        state.attributes.get(ATTR_PRESET_MODE) == BatteryCirculatorFanMode.DIRECT.value
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_PRESET_MODE: BatteryCirculatorFanMode.DIRECT.value,
            },
            blocking=True,
        )
        mock_send_command.assert_not_called()
    state = hass.states.get(entity_id)
    assert (
        state.attributes.get(ATTR_PRESET_MODE) == BatteryCirculatorFanMode.DIRECT.value
    )
    assert state.attributes.get(ATTR_PERCENTAGE) == 10
