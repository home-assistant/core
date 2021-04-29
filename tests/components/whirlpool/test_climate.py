"""Test the Whirlpool Sixth Sense climate domain."""
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import whirlpool

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
)
from homeassistant.components.whirlpool.climate import AirConEntity, async_setup_entry
from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.const import TEMP_CELSIUS


@pytest.fixture(name="aircon_api")
def aircon_api_fixture():
    """Set up air conditioner API fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.climate.Aircon"
    ) as mock_aircon_api:
        yield mock_aircon_api


@pytest.fixture(name="aircon_entity")
def aircon_entity_fixture(aircon_api):
    """Set up whirlpool air conditioner entity."""
    auth = Mock()
    return AirConEntity("TEST-SAID", auth)


async def test_async_setup_entry(hass):
    """Test the setup of the climate entities."""
    auth_mock = Mock()
    auth_mock.get_said_list.return_value = ["SAID1"]
    async_add_entities_mock = MagicMock()
    config_mock = MagicMock(
        data={
            "entry_id": "0123456789",
        }
    )
    hass.data[DOMAIN] = {config_mock.entry_id: {"auth": auth_mock}}

    await async_setup_entry(hass, config_mock, async_add_entities_mock)
    async_add_entities_mock.assert_called_once()
    entities = async_add_entities_mock.call_args.args[0]
    assert len(entities) == 1
    assert entities[0].unique_id == "SAID1"


async def test_async_setup_entry_no_appliances(hass):
    """Test the setup of the climate entities when there are no appliances available."""
    auth_mock = Mock()
    auth_mock.get_said_list.return_value = []
    async_add_entities_mock = MagicMock()
    config_mock = MagicMock(
        data={
            "entry_id": "0123456789",
        }
    )
    hass.data[DOMAIN] = {config_mock.entry_id: {"auth": auth_mock}}

    await async_setup_entry(hass, config_mock, async_add_entities_mock)
    async_add_entities_mock.assert_not_called()


async def test_name(aircon_entity, aircon_api):
    """Test name property."""
    aircon_api.return_value.connect = AsyncMock()
    aircon_api.return_value.fetch_name = AsyncMock(return_value="TestZone")

    assert aircon_entity.name == "TEST-SAID"
    await aircon_entity.async_added_to_hass()
    assert aircon_entity.name == "TestZone"


async def test_unique_id(aircon_entity, aircon_api):
    """Test name property."""
    aircon_api.return_value.said = "TEST-SAID-123"
    assert aircon_entity.unique_id == "TEST-SAID-123"


async def test_static_attributes(aircon_entity: AirConEntity, aircon_api):
    """Test getting attributes."""
    assert (
        aircon_entity.supported_features
        == SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
    )
    assert aircon_entity.hvac_modes == [
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    ]
    assert aircon_entity.fan_modes == [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW, FAN_OFF]
    assert aircon_entity.swing_modes == [SWING_HORIZONTAL, SWING_OFF]
    assert aircon_entity.temperature_unit == TEMP_CELSIUS
    assert aircon_entity.target_temperature_step == 1
    assert aircon_entity.target_humidity_step == 10
    assert aircon_entity.min_temp == 16
    assert aircon_entity.max_temp == 30


async def test_get_attributes(aircon_entity: AirConEntity, aircon_api):
    """Test getting attributes."""
    aircon_api.return_value.get_online.return_value = False
    aircon_api.return_value.get_power_on.return_value = False
    assert not aircon_entity.available
    assert aircon_entity.hvac_mode == HVAC_MODE_OFF

    aircon_api.return_value.get_online.return_value = True
    assert aircon_entity.available
    assert aircon_entity.hvac_mode == HVAC_MODE_OFF

    aircon_api.return_value.get_power_on.return_value = True

    aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Cool
    assert aircon_entity.hvac_mode == HVAC_MODE_COOL
    aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Heat
    assert aircon_entity.hvac_mode == HVAC_MODE_HEAT
    aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Fan
    assert aircon_entity.hvac_mode == HVAC_MODE_FAN_ONLY

    aircon_api.return_value.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Auto
    assert aircon_entity.fan_mode == FAN_AUTO
    aircon_api.return_value.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Low
    assert aircon_entity.fan_mode == FAN_LOW
    aircon_api.return_value.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Medium
    assert aircon_entity.fan_mode == FAN_MEDIUM
    aircon_api.return_value.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.High
    assert aircon_entity.fan_mode == FAN_HIGH
    aircon_api.return_value.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Off
    assert aircon_entity.fan_mode == FAN_OFF

    aircon_api.return_value.get_current_temp.return_value = 15
    aircon_api.return_value.get_temp.return_value = 20
    aircon_api.return_value.get_current_humidity.return_value = 80
    aircon_api.return_value.get_humidity.return_value = 50
    aircon_api.return_value.get_h_louver_swing.return_value = True
    assert aircon_entity.current_temperature == 15
    assert aircon_entity.target_temperature == 20
    assert aircon_entity.current_humidity == 80
    assert aircon_entity.target_humidity == 50
    assert aircon_entity.swing_mode == SWING_HORIZONTAL

    aircon_api.return_value.get_current_temp.return_value = 16
    aircon_api.return_value.get_temp.return_value = 21
    aircon_api.return_value.get_current_humidity.return_value = 70
    aircon_api.return_value.get_humidity.return_value = 55
    aircon_api.return_value.get_h_louver_swing.return_value = False
    assert aircon_entity.current_temperature == 16
    assert aircon_entity.target_temperature == 21
    assert aircon_entity.current_humidity == 70
    assert aircon_entity.target_humidity == 55
    assert aircon_entity.swing_mode == SWING_OFF


async def test_set_attributes(aircon_entity: AirConEntity, aircon_api):
    """Test setting attributes."""
    aircon_api.return_value.set_temp = AsyncMock()
    aircon_api.return_value.set_humidity = AsyncMock()
    aircon_api.return_value.set_mode = AsyncMock()
    aircon_api.return_value.set_fanspeed = AsyncMock()
    aircon_api.return_value.set_h_louver_swing = AsyncMock()

    await aircon_entity.async_set_temperature(temperature=15)
    aircon_api.return_value.set_temp.assert_called_once_with(15)

    await aircon_entity.async_set_humidity(80)
    aircon_api.return_value.set_humidity.assert_called_once_with(80)

    await aircon_entity.async_set_hvac_mode(HVAC_MODE_COOL)
    await aircon_entity.async_set_hvac_mode(HVAC_MODE_HEAT)
    await aircon_entity.async_set_hvac_mode(HVAC_MODE_DRY)  # this should be ignored
    await aircon_entity.async_set_hvac_mode(HVAC_MODE_FAN_ONLY)
    aircon_api.return_value.set_mode.assert_has_calls(
        [
            mock.call(whirlpool.aircon.Mode.Cool),
            mock.call(whirlpool.aircon.Mode.Heat),
            mock.call(whirlpool.aircon.Mode.Fan),
        ]
    )

    await aircon_entity.async_set_fan_mode(FAN_AUTO)
    await aircon_entity.async_set_fan_mode(FAN_LOW)
    await aircon_entity.async_set_fan_mode(FAN_MEDIUM)
    await aircon_entity.async_set_fan_mode(FAN_MIDDLE)  # this should be ignored
    await aircon_entity.async_set_fan_mode(FAN_HIGH)
    aircon_api.return_value.set_fanspeed.assert_has_calls(
        [
            mock.call(whirlpool.aircon.FanSpeed.Auto),
            mock.call(whirlpool.aircon.FanSpeed.Low),
            mock.call(whirlpool.aircon.FanSpeed.Medium),
            mock.call(whirlpool.aircon.FanSpeed.High),
        ]
    )

    await aircon_entity.async_set_swing_mode(SWING_HORIZONTAL)
    await aircon_entity.async_set_swing_mode(SWING_OFF)
    aircon_api.return_value.set_h_louver_swing.assert_has_calls(
        [mock.call(True), mock.call(False)]
    )


async def test_on_off(aircon_entity: AirConEntity, aircon_api):
    """Test turning on and off."""
    aircon_api.return_value.set_power_on = AsyncMock()
    aircon_api.return_value.set_mode = AsyncMock()

    await aircon_entity.async_turn_off()
    await aircon_entity.async_turn_on()
    aircon_api.return_value.set_power_on.assert_has_calls(
        [mock.call(False), mock.call(True)]
    )

    aircon_api.return_value.get_power_on.return_value = False
    await aircon_entity.async_set_hvac_mode(HVAC_MODE_OFF)
    await aircon_entity.async_set_hvac_mode(HVAC_MODE_COOL)
    aircon_api.return_value.set_power_on.assert_has_calls(
        [mock.call(False), mock.call(True)]
    )
