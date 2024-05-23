"""Test the Whirlpool Sixth Sense climate domain."""

from unittest.mock import MagicMock

from attr import dataclass
import pytest
import whirlpool

from homeassistant.components.climate import (
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
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntityFeature,
    HVACMode,
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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def update_ac_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_aircon_api_instance: MagicMock,
):
    """Simulate an update trigger from the API."""
    for call in mock_aircon_api_instance.register_attr_callback.call_args_list:
        update_ha_state_cb = call[0][0]
        update_ha_state_cb()
        await hass.async_block_till_done()
    return hass.states.get(entity_id)


async def test_no_appliances(
    hass: HomeAssistant, mock_appliances_manager_api: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no appliances available."""
    mock_appliances_manager_api.return_value.aircons = []
    await init_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_static_attributes(
    hass: HomeAssistant,
    mock_aircon1_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test static climate attributes."""
    await init_integration(hass)

    for entity_id in ("climate.said1", "climate.said2"):
        entry = er.async_get(hass).async_get(entity_id)
        assert entry
        assert entry.unique_id == entity_id.split(".")[1]

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == HVACMode.COOL

        attributes = state.attributes
        assert attributes[ATTR_FRIENDLY_NAME] == "TestZone"

        assert (
            attributes[ATTR_SUPPORTED_FEATURES]
            == ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        assert attributes[ATTR_HVAC_MODES] == [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.OFF,
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


async def test_dynamic_attributes(
    hass: HomeAssistant,
    mock_aircon_api_instances: MagicMock,
    mock_aircon1_api: MagicMock,
    mock_aircon2_api: MagicMock,
) -> None:
    """Test dynamic attributes."""
    await init_integration(hass)

    @dataclass
    class ClimateTestInstance:
        """Helper class for multiple climate and mock instances."""

        entity_id: str
        mock_instance: MagicMock
        mock_instance_idx: int

    for clim_test_instance in (
        ClimateTestInstance("climate.said1", mock_aircon1_api, 0),
        ClimateTestInstance("climate.said2", mock_aircon2_api, 1),
    ):
        entity_id = clim_test_instance.entity_id
        mock_instance = clim_test_instance.mock_instance
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.COOL

        mock_instance.get_power_on.return_value = False
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.state == HVACMode.OFF

        mock_instance.get_online.return_value = False
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.state == STATE_UNAVAILABLE

        mock_instance.get_power_on.return_value = True
        mock_instance.get_online.return_value = True
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.state == HVACMode.COOL

        mock_instance.get_mode.return_value = whirlpool.aircon.Mode.Heat
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.state == HVACMode.HEAT

        mock_instance.get_mode.return_value = whirlpool.aircon.Mode.Fan
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.state == HVACMode.FAN_ONLY

        mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Auto
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.attributes[ATTR_FAN_MODE] == HVACMode.AUTO

        mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Low
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.attributes[ATTR_FAN_MODE] == FAN_LOW

        mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Medium
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.attributes[ATTR_FAN_MODE] == FAN_MEDIUM

        mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.High
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

        mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Off
        state = await update_ac_state(hass, entity_id, mock_instance)
        assert state.attributes[ATTR_FAN_MODE] == FAN_OFF

        mock_instance.get_current_temp.return_value = 15
        mock_instance.get_temp.return_value = 20
        mock_instance.get_current_humidity.return_value = 80
        mock_instance.get_h_louver_swing.return_value = True
        attributes = (await update_ac_state(hass, entity_id, mock_instance)).attributes
        assert attributes[ATTR_CURRENT_TEMPERATURE] == 15
        assert attributes[ATTR_TEMPERATURE] == 20
        assert attributes[ATTR_CURRENT_HUMIDITY] == 80
        assert attributes[ATTR_SWING_MODE] == SWING_HORIZONTAL

        mock_instance.get_current_temp.return_value = 16
        mock_instance.get_temp.return_value = 21
        mock_instance.get_current_humidity.return_value = 70
        mock_instance.get_h_louver_swing.return_value = False
        attributes = (await update_ac_state(hass, entity_id, mock_instance)).attributes
        assert attributes[ATTR_CURRENT_TEMPERATURE] == 16
        assert attributes[ATTR_TEMPERATURE] == 21
        assert attributes[ATTR_CURRENT_HUMIDITY] == 70
        assert attributes[ATTR_SWING_MODE] == SWING_OFF


async def test_service_calls(
    hass: HomeAssistant,
    mock_aircon_api_instances: MagicMock,
    mock_aircon1_api: MagicMock,
    mock_aircon2_api: MagicMock,
) -> None:
    """Test controlling the entity through service calls."""
    await init_integration(hass)

    @dataclass
    class ClimateInstancesData:
        """Helper class for multiple climate and mock instances."""

        entity_id: str
        mock_instance: MagicMock

    for clim_test_instance in (
        ClimateInstancesData("climate.said1", mock_aircon1_api),
        ClimateInstancesData("climate.said2", mock_aircon2_api),
    ):
        mock_instance = clim_test_instance.mock_instance
        entity_id = clim_test_instance.entity_id

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_instance.set_power_on.assert_called_once_with(False)

        mock_instance.set_power_on.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_instance.set_power_on.assert_called_once_with(True)

        mock_instance.set_power_on.reset_mock()
        mock_instance.get_power_on.return_value = False
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_instance.set_power_on.assert_called_once_with(True)

        mock_instance.set_temp.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
            blocking=True,
        )
        mock_instance.set_temp.assert_called_once_with(15)

        mock_instance.set_mode.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_instance.set_mode.assert_called_once_with(whirlpool.aircon.Mode.Cool)

        mock_instance.set_mode.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
        mock_instance.set_mode.assert_called_once_with(whirlpool.aircon.Mode.Heat)

        mock_instance.set_mode.reset_mock()
        # HVACMode.DRY is not supported
        with pytest.raises(ValueError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.DRY},
                blocking=True,
            )
        mock_instance.set_mode.assert_not_called()

        mock_instance.set_mode.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
            blocking=True,
        )
        mock_instance.set_mode.assert_called_once_with(whirlpool.aircon.Mode.Fan)

        mock_instance.set_fanspeed.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_AUTO},
            blocking=True,
        )
        mock_instance.set_fanspeed.assert_called_once_with(
            whirlpool.aircon.FanSpeed.Auto
        )

        mock_instance.set_fanspeed.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )
        mock_instance.set_fanspeed.assert_called_once_with(
            whirlpool.aircon.FanSpeed.Low
        )

        mock_instance.set_fanspeed.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_MEDIUM},
            blocking=True,
        )
        mock_instance.set_fanspeed.assert_called_once_with(
            whirlpool.aircon.FanSpeed.Medium
        )

        mock_instance.set_fanspeed.reset_mock()
        # FAN_MIDDLE is not supported
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_MIDDLE},
                blocking=True,
            )
        mock_instance.set_fanspeed.assert_not_called()

        mock_instance.set_fanspeed.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        mock_instance.set_fanspeed.assert_called_once_with(
            whirlpool.aircon.FanSpeed.High
        )

        mock_instance.set_h_louver_swing.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_SWING_MODE: SWING_HORIZONTAL},
            blocking=True,
        )
        mock_instance.set_h_louver_swing.assert_called_with(True)

        mock_instance.set_h_louver_swing.reset_mock()
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_SWING_MODE: SWING_OFF},
            blocking=True,
        )
        mock_instance.set_h_louver_swing.assert_called_with(False)
