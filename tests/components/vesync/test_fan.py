"""Tests for VeSync air purifiers."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyvesync.vesyncfan import VeSyncAirBypass

from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.vesync.fan import (
    DOMAIN,
    FAN_MODE_AUTO,
    FAN_MODE_SLEEP,
    VS_FANS,
    VeSyncFanHA,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def test_async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    fan: VeSyncAirBypass,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the discovery mechanism can handle supported devices."""
    caplog.set_level(logging.INFO)

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_FANS] = [fan]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert len(callback.call_args.args[0]) == 1
    assert callback.call_args.args[0][0].device == fan
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__empty(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle no devices."""
    caplog.set_level(logging.INFO)

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_FANS] = []
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__invalid(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle unsupported devices."""
    caplog.set_level(logging.INFO)

    mock_fan = MagicMock()
    mock_fan.device_type = "invalid_type"
    mock_fan.device_name = "invalid_name"

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_FANS] = [mock_fan]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload:
        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert caplog.records[0].msg == "%s - Unknown device type - %s"
    assert caplog.messages[0] == "invalid_name - Unknown device type - invalid_type"


async def test_fan_entity__init(fan: VeSyncAirBypass) -> None:
    """Test the fan entity constructor."""
    entity = VeSyncFanHA(fan)

    assert entity.device == fan
    assert entity.device_class is None
    assert entity.entity_category is None
    assert hasattr(entity, "entity_description") is False
    assert entity.entity_picture is None
    assert entity.has_entity_name is False
    assert entity.icon is None
    assert entity.name == "device name"
    assert entity.supported_features == FanEntityFeature.SET_SPEED
    assert entity.unique_id == "cid1"


async def test_fan_entity__percentage(fan: VeSyncAirBypass) -> None:
    """Test the fan percentage impl."""
    entity = VeSyncFanHA(fan)
    fan.device_type = "LV-PUR131S"

    fan.mode = "mode"
    fan.fan_level = None
    assert entity.percentage is None

    fan.mode = "manual"
    fan.fan_level = None
    assert entity.percentage is None

    fan.mode = "manual"
    fan.fan_level = 1
    assert entity.percentage == 33


async def test_fan_entity__speed_count(fan: VeSyncAirBypass) -> None:
    """Test the fan speed_count impl."""
    entity = VeSyncFanHA(fan)
    fan.device_type = "LV-PUR131S"

    assert entity.speed_count == 3


async def test_fan_entity__preset_modes(fan: VeSyncAirBypass) -> None:
    """Test the fan preset_modes impl."""
    entity = VeSyncFanHA(fan)
    fan.device_type = "LV-PUR131S"

    assert entity.preset_modes == [FAN_MODE_AUTO, FAN_MODE_SLEEP]


async def test_fan_entity__preset_mode(fan: VeSyncAirBypass) -> None:
    """Test the fan preset_mode impl."""
    entity = VeSyncFanHA(fan)
    fan.device_type = "LV-PUR131S"

    fan.mode = "mode"
    assert entity.preset_mode is None
    fan.mode = FAN_MODE_AUTO
    assert entity.preset_mode == FAN_MODE_AUTO


async def test_fan_entity__unique_info(fan: VeSyncAirBypass) -> None:
    """Test the fan unique_info impl."""
    entity = VeSyncFanHA(fan)

    fan.uuid = "uuid"
    assert entity.unique_info == "uuid"


async def test_fan_entity__extra_state_attributes(
    fan: VeSyncAirBypass,
) -> None:
    """Test the fan extra_state_attributes impl."""
    entity = VeSyncFanHA(fan)

    fan.active_time = 1
    fan.screen_status = True
    fan.child_lock = True
    fan.night_light = True
    fan.mode = "mode"
    assert entity.extra_state_attributes == {
        "active_time": 1,
        "screen_status": True,
        "child_lock": True,
        "night_light": True,
        "mode": "mode",
    }


async def test_fan_entity__set_percentage_turn_off(fan: VeSyncAirBypass) -> None:
    """Test the fan set_percentage impl."""
    entity = VeSyncFanHA(fan)

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_percentage(0)
        mock_schedule.assert_called_once()

    assert fan.turn_off.call_count == 1
    assert fan.turn_on.call_count == 0


async def test_fan_entity__set_percentage_turn_on(fan: VeSyncAirBypass) -> None:
    """Test the fan set_percentage impl."""
    entity = VeSyncFanHA(fan)
    fan.is_on = False

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_percentage(10)
        mock_schedule.assert_called_once()

    fan.manual_mode.assert_called_once()
    fan.change_fan_speed.assert_called_once_with(1)
    assert fan.turn_off.call_count == 0
    assert fan.turn_on.call_count == 1


async def test_fan_entity__set_percentage_manual(fan: VeSyncAirBypass) -> None:
    """Test the fan set_percentage impl."""
    entity = VeSyncFanHA(fan)
    fan.is_on = True

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_percentage(80)
        mock_schedule.assert_called_once()

    fan.manual_mode.assert_called_once()
    fan.change_fan_speed.assert_called_once_with(3)
    assert fan.turn_off.call_count == 0
    assert fan.turn_on.call_count == 0


async def test_fan_entity__set_preset_mode_turn_on(fan: VeSyncAirBypass) -> None:
    """Test the fan set_preset_mode impl."""
    entity = VeSyncFanHA(fan)
    fan.is_on = False

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_preset_mode(FAN_MODE_AUTO)
        mock_schedule.assert_called_once()

    fan.auto_mode.assert_called_once()
    fan.sleep_mode.assert_not_called()
    assert fan.turn_on.call_count == 1


async def test_fan_entity__set_preset_mode_auto(fan: VeSyncAirBypass) -> None:
    """Test the fan set_preset_mode impl."""
    entity = VeSyncFanHA(fan)
    fan.is_on = True

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_preset_mode(FAN_MODE_AUTO)
        mock_schedule.assert_called_once()

    fan.auto_mode.assert_called_once()
    fan.sleep_mode.assert_not_called()
    assert fan.turn_on.call_count == 0


async def test_fan_entity__set_preset_mode_sleep(fan: VeSyncAirBypass) -> None:
    """Test the fan set_preset_mode impl."""
    entity = VeSyncFanHA(fan)
    fan.is_on = True

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_preset_mode(FAN_MODE_SLEEP)
        mock_schedule.assert_called_once()

    fan.auto_mode.assert_not_called()
    fan.sleep_mode.assert_called_once()
    assert fan.turn_on.call_count == 0


async def test_fan_entity__set_preset_mode_invalid(fan: VeSyncAirBypass) -> None:
    """Test the fan set_preset_mode impl."""
    entity = VeSyncFanHA(fan)

    entity._attr_available_modes = None
    with patch.object(
        entity, "schedule_update_ha_state"
    ) as mock_schedule, pytest.raises(ValueError) as ex_info:
        entity.set_preset_mode(None)
        mock_schedule.assert_not_called()
        assert (
            ex_info.value.args[0]
            == "None is not one of the valid preset modes: ['auto', 'sleep']"
        )

    with patch.object(
        entity, "schedule_update_ha_state"
    ) as mock_schedule, pytest.raises(ValueError) as ex_info:
        entity.set_preset_mode("INVALID")
        mock_schedule.assert_not_called()
        assert (
            ex_info.value.args[0]
            == "INVALID is not one of the valid preset modes: ['auto', 'sleep']"
        )

    fan.auto_mode.assert_not_called()
    fan.sleep_mode.assert_not_called()
    assert fan.turn_on.call_count == 0


async def test_fan_entity__turn_on_none(fan: VeSyncAirBypass) -> None:
    """Test the fan turn_on impl."""
    entity = VeSyncFanHA(fan)

    with patch.object(entity, "set_preset_mode") as mock_preset, patch.object(
        entity, "set_percentage"
    ) as mock_percentage:
        entity.turn_on(None, None)
        mock_preset.assert_not_called()
        mock_percentage.assert_called_once_with(50)

    assert fan.turn_on.call_count == 0


async def test_fan_entity__turn_on_both(fan: VeSyncAirBypass) -> None:
    """Test the fan turn_on impl."""
    entity = VeSyncFanHA(fan)

    with patch.object(entity, "set_preset_mode") as mock_preset, patch.object(
        entity, "set_percentage"
    ) as mock_percentage:
        entity.turn_on(10, FAN_MODE_AUTO)
        mock_preset.assert_called_once_with(FAN_MODE_AUTO)
        mock_percentage.assert_not_called()

    assert fan.turn_on.call_count == 0


async def test_fan_entity__turn_on_preset(fan: VeSyncAirBypass) -> None:
    """Test the fan turn_on impl."""
    entity = VeSyncFanHA(fan)

    with patch.object(entity, "set_preset_mode") as mock_preset, patch.object(
        entity, "set_percentage"
    ) as mock_percentage:
        entity.turn_on(None, FAN_MODE_AUTO)
        mock_preset.assert_called_once_with(FAN_MODE_AUTO)
        mock_percentage.assert_not_called()

    assert fan.turn_on.call_count == 0


async def test_fan_entity__turn_on_percent(fan: VeSyncAirBypass) -> None:
    """Test the fan turn_on impl."""
    entity = VeSyncFanHA(fan)

    with patch.object(entity, "set_preset_mode") as mock_preset, patch.object(
        entity, "set_percentage"
    ) as mock_percentage:
        entity.turn_on(20, None)
        mock_preset.assert_not_called()
        mock_percentage.assert_called_once_with(20)

    assert fan.turn_on.call_count == 0


async def test_fan_entity__is_on(fan: VeSyncAirBypass) -> None:
    """Test the fan is_on impl."""
    entity = VeSyncFanHA(fan)

    fan.device_status = "on"
    assert entity.is_on is True
    fan.device_status = "not on"
    assert entity.is_on is False
