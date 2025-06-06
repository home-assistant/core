"""Tests for the Dreo fan platform."""

from unittest.mock import MagicMock, patch

from hscloud.hscloudexception import HsCloudException
import pytest

from homeassistant.components.dreo.const import ERROR_SET_SPEED_FAILED
from homeassistant.components.dreo.fan import DreoFan, async_setup_entry
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures(
    "mock_dreo_client", "mock_dreo_devices", "mock_fan_device_data", "mock_coordinator"
)


async def test_fan_state(
    hass: HomeAssistant, setup_integration, mock_fan_entity, mock_coordinator
) -> None:
    """Test the creation and state of the fan."""
    await hass.async_block_till_done()

    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True

    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100
    assert state.attributes[ATTR_PRESET_MODE] == "auto"
    assert state.attributes[ATTR_OSCILLATING] is True


async def test_turn_on(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test turning on the fan."""

    mock_coordinator.data.is_on = False
    mock_coordinator.data.mode = None
    mock_coordinator.data.speed_percentage = 0
    mock_coordinator.data.oscillate = None
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ["fan.test_fan"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=True
    )


async def test_turn_on_with_preset_and_percentage(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test turning on the fan with preset mode and percentage."""
    mock_coordinator.data.is_on = False
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ["fan.test_fan"],
            ATTR_PRESET_MODE: "sleep",
            ATTR_PERCENTAGE: 75,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    call_args = mock_dreo_client.update_status.call_args
    assert call_args[0][0] == "test-device-id"
    assert "power_switch" in call_args[1] and call_args[1]["power_switch"] is True
    assert "mode" in call_args[1] and call_args[1]["mode"] == "sleep"
    assert "speed" in call_args[1]


async def test_turn_on_fail(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
) -> None:
    """Test turning on the fan with error."""
    mock_dreo_client.update_status.side_effect = HsCloudException("Error turning on")

    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["fan.test_fan"]},
            blocking=True,
        )

    mock_dreo_client.update_status.side_effect = None


async def test_turn_off(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test turning off the fan."""
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ["fan.test_fan"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=False
    )


async def test_turn_off_fail(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
) -> None:
    """Test turning off the fan with error."""
    mock_dreo_client.update_status.side_effect = HsCloudException("Error turning off")

    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ["fan.test_fan"]},
            blocking=True,
        )

    mock_dreo_client.update_status.side_effect = None


async def test_set_percentage(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the fan speed percentage."""
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PERCENTAGE: 75},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once()


async def test_set_percentage_zero(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the fan speed percentage to zero."""
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=False
    )


async def test_set_percentage_fail(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
) -> None:
    """Test setting the fan speed percentage with error."""
    mock_dreo_client.update_status.side_effect = HsCloudException("Error setting speed")

    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PERCENTAGE: 50},
            blocking=True,
        )

    mock_dreo_client.update_status.side_effect = None


async def test_set_preset_mode(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the preset mode."""
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PRESET_MODE: "natural"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", mode="natural"
    )


async def test_set_preset_mode_fail(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
) -> None:
    """Test setting the preset mode with error."""
    mock_dreo_client.update_status.side_effect = HsCloudException("Error setting mode")

    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )

    mock_dreo_client.update_status.side_effect = None


async def test_set_oscillate(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the oscillation."""
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_OSCILLATING: True},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", oscillate=True
    )


async def test_set_oscillate_fail(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
) -> None:
    """Test setting the oscillation with error."""
    mock_dreo_client.update_status.side_effect = HsCloudException(
        "Error setting oscillation"
    )

    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_OSCILLATE,
            {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_OSCILLATING: False},
            blocking=True,
        )

    mock_dreo_client.update_status.side_effect = None


async def test_fan_unavailable(
    hass: HomeAssistant,
    setup_integration,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test fan when coordinator is unavailable."""
    mock_coordinator.data.available = False
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_fan_setup_entry(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the fan platform."""
    runtime_data = MagicMock()
    runtime_data.devices = [
        {
            "deviceSn": "test-device-id",
            "model": "DR-HTF001S",
            "deviceName": "Test Fan",
        }
    ]
    runtime_data.coordinators = {
        "test-device-id": MagicMock(
            device_id="test-device-id",
            device_type="fan",
            device_config={"speed_range": (1, 6)},
        )
    }
    mock_config_entry.runtime_data = runtime_data

    entities = []

    def mock_async_add_entities(
        new_entities, update_before_add=True, config_subentry_id=None
    ):
        entities.extend(new_entities)

    with (
        patch("homeassistant.components.dreo.fan.DEVICE_TYPE", {"DR-HTF001S": "fan"}),
        patch("homeassistant.components.dreo.fan.FAN_DEVICE", {"type": "fan"}),
    ):
        await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities) == 1
    assert isinstance(entities[0], DreoFan)


async def test_fan_setup_entry_no_coordinator(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the fan platform with no coordinators."""
    runtime_data = MagicMock()
    runtime_data.devices = []
    runtime_data.coordinators = {}
    mock_config_entry.runtime_data = runtime_data

    entities = []

    def mock_async_add_entities(
        new_entities, update_before_add=True, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities) == 0


async def test_fan_setup_entry_unsupported_device(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the fan platform with unsupported device."""
    runtime_data = MagicMock()
    runtime_data.devices = [
        {
            "deviceSn": "test-device-id",
            "model": "UNKNOWN-MODEL",
            "deviceName": "Test Device",
        }
    ]
    runtime_data.coordinators = {
        "test-device-id": MagicMock(
            device_id="test-device-id", device_type="unsupported", device_config={}
        )
    }
    mock_config_entry.runtime_data = runtime_data

    entities = []

    def mock_async_add_entities(
        new_entities, update_before_add=True, config_subentry_id=None
    ):
        entities.extend(new_entities)

    with patch("homeassistant.components.dreo.fan.DEVICE_TYPE", {}):
        await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities) == 0


async def test_fan_setup_entry_unknown_model(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the fan platform with unknown model."""
    runtime_data = MagicMock()
    runtime_data.devices = [
        {"deviceSn": "test-device-id", "model": "DR-HTF001S", "deviceName": "Test Fan"}
    ]
    runtime_data.coordinators = {
        "test-device-id": MagicMock(
            device_id="test-device-id", device_type="fan", device_config=None
        )
    }
    mock_config_entry.runtime_data = runtime_data

    entities = []

    def mock_async_add_entities(
        new_entities, update_before_add=True, config_subentry_id=None
    ):
        entities.extend(new_entities)

    with (
        patch("homeassistant.components.dreo.fan.DEVICE_TYPE", {"DR-HTF001S": "fan"}),
        patch("homeassistant.components.dreo.fan.FAN_DEVICE", {"type": "fan"}),
    ):
        await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities) == 1
    assert isinstance(entities[0], DreoFan)


async def test_fan_setup_entry_empty_device_id(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the fan platform with empty device ID."""
    runtime_data = MagicMock()
    runtime_data.devices = [
        {"deviceSn": "", "model": "DR-HTF001S", "deviceName": "Test Fan"}
    ]
    runtime_data.coordinators = {
        "": MagicMock(device_id="", device_type="fan", device_config={})
    }
    mock_config_entry.runtime_data = runtime_data

    entities = []

    def mock_async_add_entities(
        new_entities, update_before_add=True, config_subentry_id=None
    ):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(entities) == 0


async def test_fan_initialization_with_model_config(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan initialization with model configuration."""
    mock_coordinator.device_type = "fan"
    mock_coordinator.device_config = {
        "speed_range": (1, 6),
        "preset_modes": ["auto", "sleep", "natural"],
    }

    with patch(
        "homeassistant.components.dreo.fan.FAN_DEVICE",
        {
            "config": {
                "DR-HTF001S": {
                    "speed_range": (1, 6),
                    "preset_modes": ["auto", "sleep", "natural"],
                }
            }
        },
    ):
        fan = DreoFan(
            {"deviceSn": "test-device-id", "model": "DR-HTF001S"}, mock_coordinator
        )

        assert fan.speed_count == 100
        assert fan.preset_modes == ["auto", "sleep", "natural"]
        assert fan.unique_id == "test-device-id_fan"


async def test_fan_initialization_without_model_config(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan initialization without model configuration."""
    mock_coordinator.device_type = "fan"
    mock_coordinator.device_config = {}

    with patch("homeassistant.components.dreo.fan.FAN_DEVICE", {"config": {}}):
        fan = DreoFan(
            {"deviceSn": "test-device-id", "model": "UNKNOWN"}, mock_coordinator
        )

        assert fan.speed_count == 100
        assert fan.preset_modes is None


async def test_fan_update_attributes_no_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan attribute update with no coordinator data."""
    mock_coordinator.data = None

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    assert fan.available is True


async def test_fan_update_attributes_unavailable(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan attribute update with unavailable device."""
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.available = False

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._update_attributes()

    assert fan._attr_available is False


async def test_fan_update_attributes_fan_off(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan attribute update with fan off."""
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.available = True
    mock_coordinator.data.is_on = False
    mock_coordinator.data.speed_percentage = 0
    mock_coordinator.data.mode = None
    mock_coordinator.data.oscillate = None

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._update_attributes()

    assert fan.state == STATE_OFF
    assert fan.percentage == 0
    assert fan.preset_mode is None
    assert fan.oscillating is None


async def test_fan_execute_command_math_ceil_usage(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test that execute_command uses math.ceil for speed calculation."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._low_high_range = (1, 6)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=False),
    ):
        await fan.async_set_percentage(45)

        mock_update.assert_called_once()
        call_args = mock_update.call_args[1]
        assert "speed" in call_args
        assert call_args["speed"] == 3


async def test_fan_execute_command_zero_percentage(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test execute_command with zero percentage turns off fan."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with patch.object(fan.coordinator.client, "update_status") as mock_update:
        await fan.async_set_percentage(0)

        mock_update.assert_called_once()
        call_args = mock_update.call_args[1]
        assert call_args == {"power_switch": False}


async def test_fan_execute_command_no_speed_range(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test execute_command without speed range configuration."""
    mock_coordinator.device_config = {}

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._low_high_range = None

    with patch.object(fan, "async_send_command_and_update") as mock_send:
        await fan.async_execute_fan_common_command(
            ERROR_SET_SPEED_FAILED, percentage=50
        )

        mock_send.assert_called_once_with(ERROR_SET_SPEED_FAILED, power_switch=True)


async def test_fan_execute_command_zero_speed_calculated(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test execute_command when calculated speed is zero."""
    mock_coordinator.device_config = {"speed_range": (1, 100)}

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._low_high_range = (1, 100)

    with (
        patch.object(fan, "async_send_command_and_update") as mock_send,
        patch(
            "homeassistant.util.percentage.percentage_to_ranged_value", return_value=0
        ),
        patch("math.ceil", return_value=0),
    ):
        await fan.async_execute_fan_common_command(ERROR_SET_SPEED_FAILED, percentage=1)

        mock_send.assert_called_once_with(ERROR_SET_SPEED_FAILED, power_switch=True)


async def test_fan_execute_command_fan_already_on(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test execute_command when fan is already on."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._low_high_range = (1, 6)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=True),
    ):
        await fan.async_set_percentage(50)

        mock_update.assert_called_once()
        call_args = mock_update.call_args[1]
        assert "power_switch" not in call_args
        assert "speed" in call_args


async def test_fan_update_attributes_with_fan_on_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan attribute update with fan on data."""
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.available = True
    mock_coordinator.data.is_on = True
    mock_coordinator.data.speed_percentage = 75
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.oscillate = True

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._update_attributes()

    assert fan.state == STATE_ON
    assert fan.percentage == 75
    assert fan.preset_mode == "auto"
    assert fan.oscillating is True


async def test_fan_update_attributes_available_none(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test fan attribute update when available is None."""
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.available = None
    mock_coordinator.data.is_on = True
    mock_coordinator.data.speed_percentage = 50

    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._update_attributes()

    assert fan._attr_available is False


async def test_fan_handle_coordinator_update(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test _handle_coordinator_update method."""
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with (
        patch(
            "homeassistant.components.dreo.entity.DreoEntity._handle_coordinator_update"
        ) as mock_parent,
        patch.object(fan, "_update_attributes") as mock_update,
    ):
        fan._handle_coordinator_update()

        mock_update.assert_called_once()
        mock_parent.assert_called_once()


async def test_async_set_percentage_negative(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_percentage with negative percentage."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with patch.object(fan.coordinator.client, "update_status") as mock_update:
        await fan.async_set_percentage(-10)
        mock_update.assert_called_once_with("test-device-id", power_switch=False)


async def test_async_set_percentage_zero_direct_call(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_percentage with zero percentage direct call."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with patch.object(fan.coordinator.client, "update_status") as mock_update:
        await fan.async_set_percentage(0)
        mock_update.assert_called_once_with("test-device-id", power_switch=False)


async def test_async_turn_on_direct_call(hass: HomeAssistant, mock_coordinator) -> None:
    """Test async_turn_on direct call."""
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=False),
    ):
        await fan.async_turn_on(percentage=25, preset_mode="sleep")
        mock_update.assert_called_once()


async def test_async_turn_off_direct_call(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_turn_off direct call."""
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with patch.object(fan.coordinator.client, "update_status") as mock_update:
        await fan.async_turn_off()
        mock_update.assert_called_once_with("test-device-id", power_switch=False)


async def test_async_set_preset_mode_direct_call(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_preset_mode direct call."""
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=True),
    ):
        await fan.async_set_preset_mode("natural")
        mock_update.assert_called_once_with("test-device-id", mode="natural")


async def test_async_set_percentage_positive_direct_call(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_percentage with positive percentage direct call."""
    mock_coordinator.device_config = {"speed_range": (1, 6)}
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)
    fan._low_high_range = (1, 6)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=False),
    ):
        await fan.async_set_percentage(75)
        mock_update.assert_called_once()


async def test_async_oscillate_direct_call(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_oscillate direct call."""
    fan = DreoFan({"deviceSn": "test-device-id"}, mock_coordinator)

    with (
        patch.object(fan.coordinator.client, "update_status") as mock_update,
        patch.object(DreoFan, "is_on", return_value=True),
    ):
        await fan.async_oscillate(True)
        mock_update.assert_called_once_with("test-device-id", oscillate=True)
