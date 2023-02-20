"""Tests for HomematicIP Cloud climate."""
import datetime

from homematicip.base.enums import AbsenceType
from homematicip.functionalHomes import IndoorClimateHome

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.homematicip_cloud.climate import (
    ATTR_PRESET_END_TIME,
    PERMANENT_END_TIME,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .helper import HAPID, async_manipulate_test_data, get_and_check_entity_basics


async def test_manually_configured_platform(hass: HomeAssistant) -> None:
    """Test that we do not set up an access point."""
    assert await async_setup_component(
        hass, CLIMATE_DOMAIN, {CLIMATE_DOMAIN: {"platform": HMIPC_DOMAIN}}
    )
    assert not hass.data.get(HMIPC_DOMAIN)


async def test_hmip_heating_group_heat(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipHeatingGroup."""
    entity_id = "climate.badezimmer"
    entity_name = "Badezimmer"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wandthermostat", "Heizkörperthermostat3"],
        test_groups=[entity_name],
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes["current_temperature"] == 23.8
    assert ha_state.attributes["min_temp"] == 5.0
    assert ha_state.attributes["max_temp"] == 30.0
    assert ha_state.attributes["temperature"] == 5.0
    assert ha_state.attributes["current_humidity"] == 47
    assert ha_state.attributes[ATTR_PRESET_MODE] == "STD"
    assert ha_state.attributes[ATTR_PRESET_MODES] == [PRESET_BOOST, "STD", "Winter"]

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
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("MANUAL",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "MANUAL")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.AUTO},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 5
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("AUTOMATIC",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "AUTO")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.AUTO

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
        {"entity_id": entity_id, "preset_mode": "STD"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 11
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (0,)
    await async_manipulate_test_data(hass, hmip_device, "boostMode", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == "STD"

    # Not required for hmip, but a possibility to send no temperature.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "target_temp_low": 10, "target_temp_high": 10},
        blocking=True,
    )
    # No new service call should be in mock_calls.
    assert len(hmip_device.mock_calls) == service_call_counter + 12
    # Only fire event from last async_manipulate_test_data available.
    assert hmip_device.mock_calls[-1][0] == "fire_update_event"

    await async_manipulate_test_data(hass, hmip_device, "controlMode", "ECO")
    await async_manipulate_test_data(
        hass,
        mock_hap.home.get_functionalHome(IndoorClimateHome),
        "absenceType",
        AbsenceType.VACATION,
        fire_device=hmip_device,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    await async_manipulate_test_data(hass, hmip_device, "controlMode", "ECO")
    await async_manipulate_test_data(
        hass,
        mock_hap.home.get_functionalHome(IndoorClimateHome),
        "absenceType",
        AbsenceType.PERIOD,
        fire_device=hmip_device,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "Winter"},
        blocking=True,
    )

    assert len(hmip_device.mock_calls) == service_call_counter + 18
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (1,)

    mock_hap.home.get_functionalHome(
        IndoorClimateHome
    ).absenceType = AbsenceType.PERMANENT
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "ECO")

    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_PRESET_END_TIME] == PERMANENT_END_TIME

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 20
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("MANUAL",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "MANUAL")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "Winter"},
        blocking=True,
    )

    assert len(hmip_device.mock_calls) == service_call_counter + 23
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (1,)
    hmip_device.activeProfile = hmip_device.profiles[0]
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "AUTOMATIC")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.AUTO

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": "dry"},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 24
    # Only fire event from last async_manipulate_test_data available.
    assert hmip_device.mock_calls[-1][0] == "fire_update_event"

    await async_manipulate_test_data(hass, hmip_device, "floorHeatingMode", "RADIATOR")
    await async_manipulate_test_data(hass, hmip_device, "valvePosition", 0.1)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    await async_manipulate_test_data(hass, hmip_device, "floorHeatingMode", "RADIATOR")
    await async_manipulate_test_data(hass, hmip_device, "valvePosition", 0.0)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_hmip_heating_group_cool(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipHeatingGroup."""
    entity_id = "climate.badezimmer"
    entity_name = "Badezimmer"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    hmip_device.activeProfile = hmip_device.profiles[3]
    await async_manipulate_test_data(hass, hmip_device, "cooling", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingAllowed", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingIgnored", False)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes["current_temperature"] == 23.8
    assert ha_state.attributes["min_temp"] == 5.0
    assert ha_state.attributes["max_temp"] == 30.0
    assert ha_state.attributes["temperature"] == 5.0
    assert ha_state.attributes["current_humidity"] == 47
    assert ha_state.attributes[ATTR_PRESET_MODE] == "Cool1"
    assert ha_state.attributes[ATTR_PRESET_MODES] == ["Cool1", "Cool2"]

    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("MANUAL",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "MANUAL")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.AUTO},
        blocking=True,
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "set_control_mode"
    assert hmip_device.mock_calls[-1][1] == ("AUTOMATIC",)
    await async_manipulate_test_data(hass, hmip_device, "controlMode", "AUTO")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == HVACMode.AUTO

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "Cool2"},
        blocking=True,
    )

    assert len(hmip_device.mock_calls) == service_call_counter + 6
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (4,)

    hmip_device.activeProfile = hmip_device.profiles[4]
    await async_manipulate_test_data(hass, hmip_device, "cooling", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingAllowed", False)
    await async_manipulate_test_data(hass, hmip_device, "coolingIgnored", False)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == HVACMode.OFF
    assert ha_state.attributes[ATTR_PRESET_MODE] == "none"
    assert ha_state.attributes[ATTR_PRESET_MODES] == []

    hmip_device.activeProfile = hmip_device.profiles[4]
    await async_manipulate_test_data(hass, hmip_device, "cooling", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingAllowed", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingIgnored", True)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == HVACMode.OFF
    assert ha_state.attributes[ATTR_PRESET_MODE] == "none"
    assert ha_state.attributes[ATTR_PRESET_MODES] == []

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "Cool2"},
        blocking=True,
    )

    assert len(hmip_device.mock_calls) == service_call_counter + 12
    # fire_update_event shows that set_active_profile has not been called.
    assert hmip_device.mock_calls[-1][0] == "fire_update_event"

    hmip_device.activeProfile = hmip_device.profiles[4]
    await async_manipulate_test_data(hass, hmip_device, "cooling", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingAllowed", True)
    await async_manipulate_test_data(hass, hmip_device, "coolingIgnored", False)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes[ATTR_PRESET_MODE] == "Cool2"
    assert ha_state.attributes[ATTR_PRESET_MODES] == ["Cool1", "Cool2"]

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "Cool2"},
        blocking=True,
    )

    assert len(hmip_device.mock_calls) == service_call_counter + 17
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (4,)


async def test_hmip_heating_group_heat_with_switch(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipHeatingGroup."""
    entity_id = "climate.schlafzimmer"
    entity_name = "Schlafzimmer"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wandthermostat", "Heizkörperthermostat", "Pc"],
        test_groups=[entity_name],
    )
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert hmip_device
    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes["current_temperature"] == 24.7
    assert ha_state.attributes["min_temp"] == 5.0
    assert ha_state.attributes["max_temp"] == 30.0
    assert ha_state.attributes["temperature"] == 5.0
    assert ha_state.attributes["current_humidity"] == 43
    assert ha_state.attributes[ATTR_PRESET_MODE] == "STD"
    assert ha_state.attributes[ATTR_PRESET_MODES] == [PRESET_BOOST, "STD", "P2"]


async def test_hmip_heating_group_heat_with_radiator(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipHeatingGroup."""
    entity_id = "climate.vorzimmer"
    entity_name = "Vorzimmer"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Heizkörperthermostat2"],
        test_groups=[entity_name],
    )
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert hmip_device
    assert ha_state.state == HVACMode.AUTO
    assert ha_state.attributes["current_temperature"] == 20
    assert ha_state.attributes["min_temp"] == 5.0
    assert ha_state.attributes["max_temp"] == 30.0
    assert ha_state.attributes["temperature"] == 5.0
    assert ha_state.attributes[ATTR_PRESET_MODE] is None
    assert ha_state.attributes[ATTR_PRESET_MODES] == [PRESET_NONE, PRESET_BOOST]


async def test_hmip_climate_services(
    hass: HomeAssistant, mock_hap_with_service
) -> None:
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
    assert len(home._connection.mock_calls) == 1

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_duration",
        {"duration": 60},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_duration"
    assert home.mock_calls[-1][1] == (60,)
    assert len(home._connection.mock_calls) == 2

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_period",
        {"endtime": "2019-02-17 14:00", "accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_period"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0),)
    assert len(home._connection.mock_calls) == 3

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_eco_mode_with_period",
        {"endtime": "2019-02-17 14:00"},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_absence_with_period"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0),)
    assert len(home._connection.mock_calls) == 4

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_vacation",
        {"endtime": "2019-02-17 14:00", "temperature": 18.5, "accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_vacation"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0), 18.5)
    assert len(home._connection.mock_calls) == 5

    await hass.services.async_call(
        "homematicip_cloud",
        "activate_vacation",
        {"endtime": "2019-02-17 14:00", "temperature": 18.5},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "activate_vacation"
    assert home.mock_calls[-1][1] == (datetime.datetime(2019, 2, 17, 14, 0), 18.5)
    assert len(home._connection.mock_calls) == 6

    await hass.services.async_call(
        "homematicip_cloud",
        "deactivate_eco_mode",
        {"accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "deactivate_absence"
    assert home.mock_calls[-1][1] == ()
    assert len(home._connection.mock_calls) == 7

    await hass.services.async_call(
        "homematicip_cloud", "deactivate_eco_mode", blocking=True
    )
    assert home.mock_calls[-1][0] == "deactivate_absence"
    assert home.mock_calls[-1][1] == ()
    assert len(home._connection.mock_calls) == 8

    await hass.services.async_call(
        "homematicip_cloud",
        "deactivate_vacation",
        {"accesspoint_id": HAPID},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "deactivate_vacation"
    assert home.mock_calls[-1][1] == ()
    assert len(home._connection.mock_calls) == 9

    await hass.services.async_call(
        "homematicip_cloud", "deactivate_vacation", blocking=True
    )
    assert home.mock_calls[-1][0] == "deactivate_vacation"
    assert home.mock_calls[-1][1] == ()
    assert len(home._connection.mock_calls) == 10

    not_existing_hap_id = "5555F7110000000000000001"
    await hass.services.async_call(
        "homematicip_cloud",
        "deactivate_vacation",
        {"accesspoint_id": not_existing_hap_id},
        blocking=True,
    )
    assert home.mock_calls[-1][0] == "deactivate_vacation"
    assert home.mock_calls[-1][1] == ()
    # There is no further call on connection.
    assert len(home._connection.mock_calls) == 10


async def test_hmip_heating_group_services(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipHeatingGroup services."""
    entity_id = "climate.badezimmer"
    entity_name = "Badezimmer"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert ha_state

    await hass.services.async_call(
        "homematicip_cloud",
        "set_active_climate_profile",
        {"climate_profile_index": 2, "entity_id": "climate.badezimmer"},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (1,)
    assert len(hmip_device._connection.mock_calls) == 2

    await hass.services.async_call(
        "homematicip_cloud",
        "set_active_climate_profile",
        {"climate_profile_index": 2, "entity_id": "all"},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "set_active_profile"
    assert hmip_device.mock_calls[-1][1] == (1,)
    assert len(hmip_device._connection.mock_calls) == 4
