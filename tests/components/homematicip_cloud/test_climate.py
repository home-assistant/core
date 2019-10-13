"""Tests for HomematicIP Cloud climate."""
import datetime

from homematicip.base.enums import AbsenceType
from homematicip.functionalHomes import IndoorClimateHome

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
)

from .helper import HAPID, async_manipulate_test_data, get_and_check_entity_basics


async def test_hmip_heating_group(hass, default_mock_hap):
    """Test HomematicipHeatingGroup."""
    entity_id = "climate.badezimmer"
    entity_name = "Badezimmer"
    device_model = None

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == HVAC_MODE_AUTO
    assert ha_state.attributes["current_temperature"] == 23.8
    assert ha_state.attributes["min_temp"] == 5.0
    assert ha_state.attributes["max_temp"] == 30.0
    assert ha_state.attributes["temperature"] == 5.0
    assert ha_state.attributes["current_humidity"] == 47
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert ha_state.attributes[ATTR_PRESET_MODES] == [PRESET_NONE, PRESET_BOOST]

    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 22.5},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "set_point_temperature"
    assert hmip_device.mock_calls[-1][1] == (22.5,)
    await async_manipulate_test_data(hass, hmip_device, "actualTemperature", 22.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.5

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_HEAT},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("MANUAL",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "MANUAL")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVAC_MODE_HEAT

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_AUTO},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 5
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("AUTOMATIC",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "AUTO")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVAC_MODE_AUTO

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": PRESET_BOOST},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 7
    assert hmip_device.mock_calls[-1][0] == "set_boost"
    assert hmip_device.mock_calls[-1][1] == ()
    await async_manipulate_test_data(hass, hmip_device, "boostMode", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_BOOST

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": PRESET_NONE},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 9
    assert hmip_device.mock_calls[-1][0] == "set_boost"
    assert hmip_device.mock_calls[-1][1] == (False,)
    await async_manipulate_test_data(hass, hmip_device, "boostMode", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Not required for hmip, but a posiblity to send no temperature.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "target_temp_low": 10, "target_temp_high": 10},
        blocking=True,
    )
    # No new service call should be in mock_calls.
    assert len(hmip_device.mock_calls) == service_call_counter + 10
    # Only fire event from last async_manipulate_test_data available.
    assert hmip_device.mock_calls[-1][0] == "fire_update_event"

    await async_manipulate_test_data(hass, hmip_device, "controlMode", "ECO")
    await async_manipulate_test_data(
        hass,
        default_mock_hap.home.get_functionalHome(IndoorClimateHome),
        "absenceType",
        AbsenceType.VACATION,
        fire_device=hmip_device,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    await async_manipulate_test_data(hass, hmip_device, "controlMode", "ECO")
    await async_manipulate_test_data(
        hass,
        default_mock_hap.home.get_functionalHome(IndoorClimateHome),
        "absenceType",
        AbsenceType.PERIOD,
        fire_device=hmip_device,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_ECO


async def test_hmip_climate_services(hass, mock_hap_with_service):
    """Test HomematicipHeatingGroup."""

    home = mock_hap_with_service.home

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_duration",
        {"duration": 60, "accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_duration"
    assert home.mock_calls[-1][1] == (60,)

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_duration",
        {"duration": 60},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_duration"
    assert home.mock_calls[-1][1] == (60,)

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_period",
        {"endtime": "2019-02-17 14:00", "accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_period"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0),)

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_period",
        {"endtime": "2019-02-17 14:00"},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_period"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0),)

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_vacation",
        {"endtime": "2019-02-17 14:00", "temperature": 18.5, "accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_vacation"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0), 18.5)

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_vacation",
        {"endtime": "2019-02-17 14:00", "temperature": 18.5},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_vacation"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0), 18.5)

    await hass.services.async_call(
        "homematicip_cloud",
        "deactivate_eco_mode",
        {"accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "deactivate_absence"
    assert home.mock_calls[-1][1] == ()

    await hass.services.async_call(
        "homematicip_cloud", "deactivate_eco_mode", blocking=True
    )
    assert home.mock_calls[-1][0] == "deactivate_absence"
    assert home.mock_calls[-1][1] == ()

    await hass.services.async_call(
        "homematicip_cloud",
        "deactivate_vacation",
        {"accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "deactivate_vacation"
    assert home.mock_calls[-1][1] == ()

    await hass.services.async_call(
        "homematicip_cloud", "deactivate_vacation", blocking=True
    )
    assert home.mock_calls[-1][0] == "deactivate_vacation"
    assert home.mock_calls[-1][1] == ()
