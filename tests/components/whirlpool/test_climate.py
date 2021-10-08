"""Test the Whirlpool Sixth Sense climate domain."""
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import whirlpool

from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def update_ac_state(hass: HomeAssistant, mock_aircon_api: MagicMock):
    """Simulate an update trigger from the API."""
    update_ha_state_cb = mock_aircon_api.call_args.args[2]
    update_ha_state_cb()
    await hass.async_block_till_done()
    return hass.states.get("climate.said1")


async def test_no_appliances(hass: HomeAssistant, mock_auth_api: MagicMock):
    """Test the setup of the climate entities when there are no appliances available."""
    mock_auth_api.return_value.get_said_list.return_value = []
    await init_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_name_fallback_on_exception(
    hass: HomeAssistant, mock_aircon_api: MagicMock
):
    """Test name property."""
    mock_aircon_api.return_value.fetch_name = AsyncMock(
        side_effect=aiohttp.ClientError()
    )

    await init_integration(hass)
    state = hass.states.get("climate.said1")
    assert state.attributes[ATTR_FRIENDLY_NAME] == "said1"


async def test_static_attributes(hass: HomeAssistant, mock_aircon_api: MagicMock):
    """Test static climate attributes."""
    await init_integration(hass)

    entry = er.async_get(hass).async_get("climate.said1")
    assert entry
    assert entry.unique_id == "said1"

    state = hass.states.get("climate.said1")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == HVAC_MODE_COOL

    attributes = state.attributes
    assert attributes[ATTR_FRIENDLY_NAME] == "TestZone"

    assert (
        attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
    )
    assert attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    ]
    assert attributes[ATTR_FAN_MODES] == [
        FAN_AUTO,
        FAN_HIGH,
        FAN_MEDIUM,
        FAN_LOW,
        FAN_OFF,
    ]
    assert attributes[ATTR_SWING_MODES] == [SWING_HORIZONTAL, SWING_OFF]
    assert attributes[ATTR_TARGET_TEMP_STEP] == 1
    assert attributes[ATTR_MIN_TEMP] == 16
    assert attributes[ATTR_MAX_TEMP] == 30


async def test_dynamic_attributes(hass: HomeAssistant, mock_aircon_api: MagicMock):
    """Test dynamic attributes."""
    await init_integration(hass)

    state = hass.states.get("climate.said1")
    assert state is not None
    assert state.state == HVAC_MODE_COOL

    mock_aircon_api.return_value.get_power_on.return_value = False
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.state == HVAC_MODE_OFF

    mock_aircon_api.return_value.get_online.return_value = False
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.state == STATE_UNAVAILABLE

    mock_aircon_api.return_value.get_power_on.return_value = True
    mock_aircon_api.return_value.get_online.return_value = True
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.state == HVAC_MODE_COOL

    mock_aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Heat
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.state == HVAC_MODE_HEAT

    mock_aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Fan
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.state == HVAC_MODE_FAN_ONLY

    mock_aircon_api.return_value.get_fanspeed.return_value = (
        whirlpool.aircon.FanSpeed.Auto
    )
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.attributes[ATTR_FAN_MODE] == HVAC_MODE_AUTO

    mock_aircon_api.return_value.get_fanspeed.return_value = (
        whirlpool.aircon.FanSpeed.Low
    )
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.attributes[ATTR_FAN_MODE] == FAN_LOW

    mock_aircon_api.return_value.get_fanspeed.return_value = (
        whirlpool.aircon.FanSpeed.Medium
    )
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.attributes[ATTR_FAN_MODE] == FAN_MEDIUM

    mock_aircon_api.return_value.get_fanspeed.return_value = (
        whirlpool.aircon.FanSpeed.High
    )
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

    mock_aircon_api.return_value.get_fanspeed.return_value = (
        whirlpool.aircon.FanSpeed.Off
    )
    state = await update_ac_state(hass, mock_aircon_api)
    assert state.attributes[ATTR_FAN_MODE] == FAN_OFF

    mock_aircon_api.return_value.get_current_temp.return_value = 15
    mock_aircon_api.return_value.get_temp.return_value = 20
    mock_aircon_api.return_value.get_current_humidity.return_value = 80
    mock_aircon_api.return_value.get_h_louver_swing.return_value = True
    attributes = (await update_ac_state(hass, mock_aircon_api)).attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] == 15
    assert attributes[ATTR_TEMPERATURE] == 20
    assert attributes[ATTR_CURRENT_HUMIDITY] == 80
    assert attributes[ATTR_SWING_MODE] == SWING_HORIZONTAL

    mock_aircon_api.return_value.get_current_temp.return_value = 16
    mock_aircon_api.return_value.get_temp.return_value = 21
    mock_aircon_api.return_value.get_current_humidity.return_value = 70
    mock_aircon_api.return_value.get_h_louver_swing.return_value = False
    attributes = (await update_ac_state(hass, mock_aircon_api)).attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] == 16
    assert attributes[ATTR_TEMPERATURE] == 21
    assert attributes[ATTR_CURRENT_HUMIDITY] == 70
    assert attributes[ATTR_SWING_MODE] == SWING_OFF


async def test_service_calls(hass: HomeAssistant, mock_aircon_api: MagicMock):
    """Test controlling the entity through service calls."""
    await init_integration(hass)
    mock_aircon_api.return_value.set_power_on = AsyncMock()
    mock_aircon_api.return_value.set_mode = AsyncMock()
    mock_aircon_api.return_value.set_temp = AsyncMock()
    mock_aircon_api.return_value.set_humidity = AsyncMock()
    mock_aircon_api.return_value.set_mode = AsyncMock()
    mock_aircon_api.return_value.set_fanspeed = AsyncMock()
    mock_aircon_api.return_value.set_h_louver_swing = AsyncMock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "climate.said1"},
        blocking=True,
    )
    mock_aircon_api.return_value.set_power_on.assert_called_once_with(False)

    mock_aircon_api.return_value.set_power_on.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "climate.said1"},
        blocking=True,
    )
    mock_aircon_api.return_value.set_power_on.assert_called_once_with(True)

    mock_aircon_api.return_value.set_power_on.reset_mock()
    mock_aircon_api.return_value.get_power_on.return_value = False
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        blocking=True,
    )
    mock_aircon_api.return_value.set_power_on.assert_called_once_with(True)

    mock_aircon_api.return_value.set_temp.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    mock_aircon_api.return_value.set_temp.assert_called_once_with(15)

    mock_aircon_api.return_value.set_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        blocking=True,
    )
    mock_aircon_api.return_value.set_mode.assert_called_once_with(
        whirlpool.aircon.Mode.Cool
    )

    mock_aircon_api.return_value.set_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    mock_aircon_api.return_value.set_mode.assert_called_once_with(
        whirlpool.aircon.Mode.Heat
    )

    mock_aircon_api.return_value.set_mode.reset_mock()
    # HVAC_MODE_DRY should be ignored
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_HVAC_MODE: HVAC_MODE_DRY},
        blocking=True,
    )
    mock_aircon_api.return_value.set_mode.assert_not_called()

    mock_aircon_api.return_value.set_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_HVAC_MODE: HVAC_MODE_FAN_ONLY},
        blocking=True,
    )
    mock_aircon_api.return_value.set_mode.assert_called_once_with(
        whirlpool.aircon.Mode.Fan
    )

    mock_aircon_api.return_value.set_fanspeed.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )
    mock_aircon_api.return_value.set_fanspeed.assert_called_once_with(
        whirlpool.aircon.FanSpeed.Auto
    )

    mock_aircon_api.return_value.set_fanspeed.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
    mock_aircon_api.return_value.set_fanspeed.assert_called_once_with(
        whirlpool.aircon.FanSpeed.Low
    )

    mock_aircon_api.return_value.set_fanspeed.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_FAN_MODE: FAN_MEDIUM},
        blocking=True,
    )
    mock_aircon_api.return_value.set_fanspeed.assert_called_once_with(
        whirlpool.aircon.FanSpeed.Medium
    )

    mock_aircon_api.return_value.set_fanspeed.reset_mock()
    # FAN_MIDDLE should be ignored
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_FAN_MODE: FAN_MIDDLE},
        blocking=True,
    )
    mock_aircon_api.return_value.set_fanspeed.assert_not_called()

    mock_aircon_api.return_value.set_fanspeed.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_FAN_MODE: FAN_HIGH},
        blocking=True,
    )
    mock_aircon_api.return_value.set_fanspeed.assert_called_once_with(
        whirlpool.aircon.FanSpeed.High
    )

    mock_aircon_api.return_value.set_h_louver_swing.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_SWING_MODE: SWING_HORIZONTAL},
        blocking=True,
    )
    mock_aircon_api.return_value.set_h_louver_swing.assert_called_with(True)

    mock_aircon_api.return_value.set_h_louver_swing.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.said1", ATTR_SWING_MODE: SWING_OFF},
        blocking=True,
    )
    mock_aircon_api.return_value.set_h_louver_swing.assert_called_with(False)
