"""Tests for VeSync humidifiers."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyvesync.vesyncfan import VeSyncHumid200300S

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.components.vesync.humidifier import (
    DOMAIN,
    MAX_HUMIDITY,
    MIN_HUMIDITY,
    VS_HUMIDIFIERS,
    VeSyncHumidifierEntityDescription,
    VeSyncHumidifierHA,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def test_async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    humid_features,
    humidifier: VeSyncHumid200300S,
    humidifier_nightlight: VeSyncHumid200300S,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the discovery mechanism can handle supported devices."""
    caplog.set_level(logging.INFO)

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_HUMIDIFIERS] = [humidifier, humidifier_nightlight]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload, patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert len(callback.call_args.args[0]) == 2
    assert callback.call_args.args[0][0].device == humidifier
    assert callback.call_args.args[0][1].device == humidifier_nightlight
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__empty(
    hass: HomeAssistant, config_entry, humid_features, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle no devices."""
    caplog.set_level(logging.INFO)

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_HUMIDIFIERS] = []
    with patch.object(config_entry, "async_on_unload") as mock_on_unload, patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert len(caplog.records) == 0


async def test_async_setup_entry__invalid(
    hass: HomeAssistant, config_entry, humid_features, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle unsupported devices."""
    caplog.set_level(logging.INFO)

    mock_humidifier = MagicMock()
    mock_humidifier.device_type = "invalid_type"
    mock_humidifier.device_name = "invalid_name"

    callback = AsyncMock(AddEntitiesCallback)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_HUMIDIFIERS] = [mock_humidifier]
    with patch.object(config_entry, "async_on_unload") as mock_on_unload, patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        await async_setup_entry(hass, config_entry, callback)
        await hass.async_block_till_done()

    callback.assert_called_once()
    assert callback.call_args.args == ([],)
    assert callback.call_args.kwargs == {"update_before_add": True}
    mock_on_unload.assert_called_once()
    assert caplog.records[0].msg == "%s - Unknown device type - %s"
    assert caplog.messages[0] == "invalid_name - Unknown device type - invalid_type"


async def test_humidifier_entity__init(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier entity constructor."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    assert entity.available_modes == ["normal"]
    assert entity.device == humidifier
    assert entity.device_class == HumidifierDeviceClass.HUMIDIFIER
    assert entity.entity_category is None
    assert entity.entity_description == description
    assert entity.entity_picture == "device image"
    assert entity.has_entity_name is False
    assert entity.icon == "mdi:air-humidifier"
    assert entity.max_humidity == MAX_HUMIDITY
    assert entity.min_humidity == MIN_HUMIDITY
    assert entity.mode == "normal"
    assert entity.name == "device name"
    assert entity.supported_features == HumidifierEntityFeature.MODES
    assert entity.target_humidity == 50
    assert entity.unique_id == "cid1"


async def test_humidifier_entity__unique_info(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier unique_info impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    humidifier.uuid = "uuid"
    assert entity.unique_info == "uuid"


async def test_humidifier_entity__extra_state_attributes(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier extra_state_attributes impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    humidifier.warm_mist_feature = True
    assert entity.extra_state_attributes == {"warm_mist_feature": True}


async def test_humidifier_entity__is_on(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier is_on impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    humidifier.is_on = True
    assert entity.is_on is True
    humidifier.is_on = False
    assert entity.is_on is False


async def test_humidifier_entity__turn_on(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier turn_on impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.turn_on()
        mock_schedule.assert_called_once()

    assert humidifier.turn_on.call_count == 1


async def test_humidifier_entity__mode(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    entity._attr_available_modes = None
    assert entity.mode is None
    entity._attr_available_modes = ["None"]
    assert entity.mode is None
    entity._attr_available_modes = ["None", "normal"]
    assert entity.mode == "normal"


async def test_humidifier_entity__set_mode_normal_when_off(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = False

    entity._attr_available_modes = [MODE_NORMAL]
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_mode(MODE_NORMAL)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_called_once()
    humidifier.set_manual_mode.assert_called_once()
    humidifier.set_humidity_mode.assert_not_called()
    humidifier.set_auto_mode.assert_not_called()
    assert entity._attr_mode == MODE_NORMAL


async def test_humidifier_entity__set_mode_normal(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = True

    entity._attr_available_modes = [MODE_NORMAL]
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_mode(MODE_NORMAL)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_not_called()
    humidifier.set_manual_mode.assert_called_once()
    humidifier.set_humidity_mode.assert_not_called()
    humidifier.set_auto_mode.assert_not_called()
    assert entity._attr_mode == MODE_NORMAL


async def test_humidifier_entity__set_mode_sleep(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = True

    entity._attr_available_modes = [MODE_SLEEP]
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_mode(MODE_SLEEP)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_not_called()
    humidifier.set_manual_mode.assert_not_called()
    humidifier.set_humidity_mode.assert_called_once()
    humidifier.set_auto_mode.assert_not_called()
    assert entity._attr_mode == MODE_SLEEP


async def test_humidifier_entity__set_mode_auto(humidifier: VeSyncHumid200300S) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = True

    entity._attr_available_modes = [MODE_AUTO]
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_mode(MODE_AUTO)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_not_called()
    humidifier.set_manual_mode.assert_not_called()
    humidifier.set_humidity_mode.assert_not_called()
    humidifier.set_auto_mode.assert_called_once()
    assert entity._attr_mode == MODE_AUTO


async def test_humidifier_entity__set_mode_validation(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    entity._attr_available_modes = None
    with pytest.raises(ValueError) as ex_info:
        entity.set_mode("normal")
        assert ex_info.value.args[0] == "No available modes were specified"

    entity._attr_available_modes = ["normal"]
    with pytest.raises(ValueError) as ex_info:
        entity.set_mode(None)
        assert (
            ex_info.value.args[0]
            == "None is not one of the available modes: ['normal']"
        )
    with pytest.raises(ValueError) as ex_info:
        entity.set_mode("auto")
        assert (
            ex_info.value.args[0]
            == "auto is not one of the available modes: ['normal']"
        )


async def test_humidifier_entity__target_humidity(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier is_on impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    humidifier.auto_humidity = 20
    assert entity.target_humidity == 20


async def test_humidifier_entity__set_humidity(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = True

    entity._attr_min_humidity = 30
    entity._attr_max_humidity = 80
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_humidity(50)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_not_called()
    humidifier.set_humidity.assert_called_once_with(50)
    assert entity._attr_mode == MODE_NORMAL


async def test_humidifier_entity__set_humidity_when_off(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)
    humidifier.is_on = False

    entity._attr_min_humidity = 30
    entity._attr_max_humidity = 80
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.set_humidity(50)
        mock_schedule.assert_called_once()

    humidifier.turn_on.assert_called_once()
    humidifier.set_humidity.assert_called_once_with(50)
    assert entity._attr_mode == MODE_NORMAL


async def test_humidifier_entity__set_humidity_validation(
    humidifier: VeSyncHumid200300S,
) -> None:
    """Test the humidifier mode impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    entity._attr_min_humidity = 30
    entity._attr_max_humidity = 80
    with pytest.raises(ValueError) as ex_info:
        entity.set_humidity(29)
        assert ex_info.value.args[0] == "29 is not between 30 and 80 (inclusive)"

    with pytest.raises(ValueError) as ex_info:
        entity.set_humidity(81)
        assert ex_info.value.args[0] == "81 is not between 30 and 80 (inclusive)"
