"""Tests for HomematicIP Cloud sensor."""

from homematicip.base.enums import ValveState

from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.homematicip_cloud.entity import (
    ATTR_CONFIG_PENDING,
    ATTR_DEVICE_OVERHEATED,
    ATTR_DEVICE_OVERLOADED,
    ATTR_DEVICE_UNTERVOLTAGE,
    ATTR_DUTY_CYCLE_REACHED,
    ATTR_RSSI_DEVICE,
    ATTR_RSSI_PEER,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.components.homematicip_cloud.sensor import (
    ATTR_CURRENT_ILLUMINATION,
    ATTR_HIGHEST_ILLUMINATION,
    ATTR_LEFT_COUNTER,
    ATTR_LOWEST_ILLUMINATION,
    ATTR_RIGHT_COUNTER,
    ATTR_TEMPERATURE_OFFSET,
    ATTR_WIND_DIRECTION,
    ATTR_WIND_DIRECTION_VARIATION,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .helper import HomeFactory, async_manipulate_test_data, get_and_check_entity_basics


async def test_manually_configured_platform(hass: HomeAssistant) -> None:
    """Test that we do not set up an access point."""
    assert await async_setup_component(
        hass, SENSOR_DOMAIN, {SENSOR_DOMAIN: {"platform": HMIPC_DOMAIN}}
    )
    assert not hass.data.get(HMIPC_DOMAIN)


async def test_hmip_accesspoint_status(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSwitch."""
    entity_id = "sensor.home_control_access_point_duty_cycle"
    entity_name = "HOME_CONTROL_ACCESS_POINT Duty Cycle"
    device_model = "HmIP-HAP"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["HOME_CONTROL_ACCESS_POINT"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert hmip_device
    assert ha_state.state == "8.0"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE


async def test_hmip_heating_thermostat(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipHeatingThermostat."""
    entity_id = "sensor.heizkorperthermostat_heating"
    entity_name = "Heizkörperthermostat Heating"
    device_model = "HMIP-eTRV"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Heizkörperthermostat"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "0"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    await async_manipulate_test_data(hass, hmip_device, "valvePosition", 0.37)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "37"

    await async_manipulate_test_data(hass, hmip_device, "valveState", "nn")
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN

    await async_manipulate_test_data(
        hass, hmip_device, "valveState", ValveState.ADAPTION_DONE
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "37"

    await async_manipulate_test_data(hass, hmip_device, "lowBat", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes["icon"] == "mdi:battery-outline"


async def test_hmip_humidity_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipHumiditySensor."""
    entity_id = "sensor.bwth_1_humidity"
    entity_name = "BWTH 1 Humidity"
    device_model = "HmIP-BWTH"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["BWTH 1"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "40"
    assert ha_state.attributes["unit_of_measurement"] == PERCENTAGE
    await async_manipulate_test_data(hass, hmip_device, "humidity", 45)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "45"
    # test common attributes
    assert ha_state.attributes[ATTR_RSSI_DEVICE] == -76
    assert ha_state.attributes[ATTR_RSSI_PEER] == -77


async def test_hmip_temperature_sensor1(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureSensor."""
    entity_id = "sensor.bwth_1_temperature"
    entity_name = "BWTH 1 Temperature"
    device_model = "HmIP-BWTH"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["BWTH 1"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "21.0"
    assert ha_state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "actualTemperature", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"

    assert not ha_state.attributes.get("temperature_offset")
    await async_manipulate_test_data(hass, hmip_device, "temperatureOffset", 10)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_TEMPERATURE_OFFSET] == 10


async def test_hmip_temperature_sensor2(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureSensor."""
    entity_id = "sensor.heizkorperthermostat_temperature"
    entity_name = "Heizkörperthermostat Temperature"
    device_model = "HMIP-eTRV"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Heizkörperthermostat"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "20.0"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "valveActualTemperature", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"

    assert not ha_state.attributes.get(ATTR_TEMPERATURE_OFFSET)
    await async_manipulate_test_data(hass, hmip_device, "temperatureOffset", 10)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_TEMPERATURE_OFFSET] == 10


async def test_hmip_temperature_sensor3(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureSensor."""
    entity_id = "sensor.raumbediengerat_analog_temperature"
    entity_name = "Raumbediengerät Analog Temperature"
    device_model = "ALPHA-IP-RBGa"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Raumbediengerät Analog"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "23.3"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "actualTemperature", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"

    assert not ha_state.attributes.get(ATTR_TEMPERATURE_OFFSET)
    await async_manipulate_test_data(hass, hmip_device, "temperatureOffset", 10)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_TEMPERATURE_OFFSET] == 10


async def test_hmip_thermostat_evo_heating(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipHeatingThermostat for HmIP-eTRV-E."""
    entity_id = "sensor.thermostat_evo_heating"
    entity_name = "thermostat_evo Heating"
    device_model = "HmIP-eTRV-E"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["thermostat_evo"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "33"
    await async_manipulate_test_data(hass, hmip_device, "valvePosition", 0.4)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ha_state.state == "40"


async def test_hmip_thermostat_evo_temperature(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureSensor."""
    entity_id = "sensor.thermostat_evo_temperature"
    entity_name = "thermostat_evo Temperature"
    device_model = "HmIP-eTRV-E"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["thermostat_evo"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "18.7"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "valveActualTemperature", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"

    await async_manipulate_test_data(hass, hmip_device, "temperatureOffset", 0.7)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_TEMPERATURE_OFFSET] == 0.7


async def test_hmip_power_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipPowerSensor."""
    entity_id = "sensor.flur_oben_power"
    entity_name = "Flur oben Power"
    device_model = "HmIP-BSM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Flur oben"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "0.0"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
    await async_manipulate_test_data(hass, hmip_device, "currentPowerConsumption", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"
    # test common attributes
    assert not ha_state.attributes.get(ATTR_DEVICE_OVERHEATED)
    assert not ha_state.attributes.get(ATTR_DEVICE_OVERLOADED)
    assert not ha_state.attributes.get(ATTR_DEVICE_UNTERVOLTAGE)
    assert not ha_state.attributes.get(ATTR_DUTY_CYCLE_REACHED)
    assert not ha_state.attributes.get(ATTR_CONFIG_PENDING)
    await async_manipulate_test_data(hass, hmip_device, "deviceOverheated", True)
    await async_manipulate_test_data(hass, hmip_device, "deviceOverloaded", True)
    await async_manipulate_test_data(hass, hmip_device, "deviceUndervoltage", True)
    await async_manipulate_test_data(hass, hmip_device, "dutyCycle", True)
    await async_manipulate_test_data(hass, hmip_device, "configPending", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_DEVICE_OVERHEATED]
    assert ha_state.attributes[ATTR_DEVICE_OVERLOADED]
    assert ha_state.attributes[ATTR_DEVICE_UNTERVOLTAGE]
    assert ha_state.attributes[ATTR_DUTY_CYCLE_REACHED]
    assert ha_state.attributes[ATTR_CONFIG_PENDING]


async def test_hmip_illuminance_sensor1(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipIlluminanceSensor."""
    entity_id = "sensor.wettersensor_illuminance"
    entity_name = "Wettersensor Illuminance"
    device_model = "HmIP-SWO-B"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wettersensor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "4890.0"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == LIGHT_LUX
    await async_manipulate_test_data(hass, hmip_device, "illumination", 231)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "231"


async def test_hmip_illuminance_sensor2(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipIlluminanceSensor."""
    entity_id = "sensor.lichtsensor_nord_illuminance"
    entity_name = "Lichtsensor Nord Illuminance"
    device_model = "HmIP-SLO"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Lichtsensor Nord"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "807.3"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == LIGHT_LUX
    await async_manipulate_test_data(hass, hmip_device, "averageIllumination", 231)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "231"
    assert ha_state.attributes[ATTR_CURRENT_ILLUMINATION] == 785.2
    assert ha_state.attributes[ATTR_HIGHEST_ILLUMINATION] == 837.1
    assert ha_state.attributes[ATTR_LOWEST_ILLUMINATION] == 785.2


async def test_hmip_windspeed_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipWindspeedSensor."""
    entity_id = "sensor.wettersensor_pro_windspeed"
    entity_name = "Wettersensor - pro Windspeed"
    device_model = "HmIP-SWO-PR"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wettersensor - pro"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "2.6"
    assert (
        ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.KILOMETERS_PER_HOUR
    )
    assert ha_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    await async_manipulate_test_data(hass, hmip_device, "windSpeed", 9.4)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "9.4"

    assert ha_state.attributes[ATTR_WIND_DIRECTION_VARIATION] == 56.25
    assert ha_state.attributes[ATTR_WIND_DIRECTION] == "WNW"

    wind_directions = {
        25: "NNE",
        37.5: "NE",
        70: "ENE",
        92.5: "E",
        115: "ESE",
        137.5: "SE",
        160: "SSE",
        182.5: "S",
        205: "SSW",
        227.5: "SW",
        250: "WSW",
        272.5: UnitOfPower.WATT,
        295: "WNW",
        317.5: "NW",
        340: "NNW",
        0: "N",
    }

    for direction, txt in wind_directions.items():
        await async_manipulate_test_data(hass, hmip_device, "windDirection", direction)
        ha_state = hass.states.get(entity_id)
        assert ha_state.attributes[ATTR_WIND_DIRECTION] == txt


async def test_hmip_today_rain_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTodayRainSensor."""
    entity_id = "sensor.weather_sensor_plus_today_rain"
    entity_name = "Weather Sensor – plus Today Rain"
    device_model = "HmIP-SWO-PL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Weather Sensor – plus"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "3.9"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert ha_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    await async_manipulate_test_data(hass, hmip_device, "todayRainCounter", 14.2)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "14.2"


async def test_hmip_temperature_external_sensor_channel_1(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureDifferenceSensor Channel 1 HmIP-STE2-PCB."""
    entity_id = "sensor.ste2_channel_1_temperature"
    entity_name = "STE2 Channel 1 Temperature"
    device_model = "HmIP-STE2-PCB"

    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_devices=["STE2"])
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)

    await async_manipulate_test_data(hass, hmip_device, "temperatureExternalOne", 25.4)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "25.4"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "temperatureExternalOne", 23.5)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.5"


async def test_hmip_temperature_external_sensor_channel_2(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureDifferenceSensor Channel 2 HmIP-STE2-PCB."""
    entity_id = "sensor.ste2_channel_2_temperature"
    entity_name = "STE2 Channel 2 Temperature"
    device_model = "HmIP-STE2-PCB"

    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_devices=["STE2"])
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)

    await async_manipulate_test_data(hass, hmip_device, "temperatureExternalTwo", 22.4)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "22.4"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(hass, hmip_device, "temperatureExternalTwo", 23.4)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "23.4"


async def test_hmip_temperature_external_sensor_delta(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTemperatureDifferenceSensor Delta HmIP-STE2-PCB."""
    entity_id = "sensor.ste2_delta_temperature"
    entity_name = "STE2 Delta Temperature"
    device_model = "HmIP-STE2-PCB"

    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_devices=["STE2"])
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)

    await async_manipulate_test_data(hass, hmip_device, "temperatureExternalDelta", 0.4)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "0.4"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    await async_manipulate_test_data(
        hass, hmip_device, "temperatureExternalDelta", -0.5
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "-0.5"


async def test_hmip_passage_detector_delta_counter(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipPassageDetectorDeltaCounter."""
    entity_id = "sensor.spdr_1"
    entity_name = "SPDR_1"
    device_model = "HmIP-SPDR"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "164"
    assert ha_state.attributes[ATTR_LEFT_COUNTER] == 966
    assert ha_state.attributes[ATTR_RIGHT_COUNTER] == 802
    await async_manipulate_test_data(hass, hmip_device, "leftRightCounterDelta", 190)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "190"


async def test_hmip_floor_terminal_block_mechanic_channel_1_valve_position(
    hass: HomeAssistant, default_mock_hap_factory: HomematicipHAP
) -> None:
    """Test HomematicipFloorTerminalBlockMechanicChannelValve Channel 1 HmIP-FALMOT-C12."""
    entity_id = "sensor.heizkreislauf_1_og_bad_r"
    entity_name = "Heizkreislauf (1) OG Bad r"
    device_model = "HmIP-FALMOT-C12"

    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Fu\u00dfbodenheizungsaktor"]
    )
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    hmip_device = mock_hap.hmip_device_by_entity_id.get(entity_id)

    assert ha_state.state == "48"
    assert ha_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    await async_manipulate_test_data(hass, hmip_device, "valvePosition", 0.36)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == "36"

    await async_manipulate_test_data(hass, hmip_device, "configPending", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes["icon"] == "mdi:alert-circle"

    await async_manipulate_test_data(hass, hmip_device, "configPending", False)
    await async_manipulate_test_data(
        hass, hmip_device, "valveState", ValveState.ADAPTION_IN_PROGRESS
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes["icon"] == "mdi:alert"

    await async_manipulate_test_data(
        hass, hmip_device, "valveState", ValveState.ADAPTION_DONE
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes["icon"] == "mdi:heating-coil"


async def test_hmip_esi_iec_current_power_consumption(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC currentPowerConsumption Sensor."""
    entity_id = "sensor.esi_iec_currentPowerConsumption"
    entity_name = "esi_iec CurrentPowerConsumption"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_iec"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "432"


async def test_hmip_esi_iec_energy_counter_usage_high_tariff(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC ENERGY_COUNTER_USAGE_HIGH_TARIFF."""
    entity_id = "sensor.esi_iec_energy_counter_usage_high_tariff"
    entity_name = "esi_iec ENERGY_COUNTER_USAGE_HIGH_TARIFF"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_iec"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "194.0"


async def test_hmip_esi_iec_energy_counter_usage_low_tariff(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC ENERGY_COUNTER_USAGE_LOW_TARIFF."""
    entity_id = "sensor.esi_iec_energy_counter_usage_low_tariff"
    entity_name = "esi_iec ENERGY_COUNTER_USAGE_LOW_TARIFF"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_iec"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "0.0"


async def test_hmip_esi_iec_energy_counter_input_single_tariff(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC ENERGY_COUNTER_INPUT_SINGLE_TARIFF."""
    entity_id = "sensor.esi_iec_energy_counter_input_single_tariff"
    entity_name = "esi_iec ENERGY_COUNTER_INPUT_SINGLE_TARIFF"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_iec"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "3.0"


async def test_hmip_esi_iec_unknown_channel(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test devices are loaded partially."""
    not_existing_entity_id = "sensor.esi_iec2_energy_counter_input_single_tariff"
    existing_entity_id = "sensor.esi_iec2_energy_counter_usage_high_tariff"
    await default_mock_hap_factory.async_get_mock_hap(test_devices=["esi_iec2"])

    not_existing_ha_state = hass.states.get(not_existing_entity_id)
    existing_ha_state = hass.states.get(existing_entity_id)

    assert not_existing_ha_state is None
    assert existing_ha_state.state == "194.0"


async def test_hmip_esi_gas_current_gas_flow(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC CurrentGasFlow."""
    entity_id = "sensor.esi_gas_currentgasflow"
    entity_name = "esi_gas CurrentGasFlow"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_gas"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "1.03"


async def test_hmip_esi_gas_gas_volume(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC GasVolume."""
    entity_id = "sensor.esi_gas_gasvolume"
    entity_name = "esi_gas GasVolume"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_gas"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "1019.26"


async def test_hmip_esi_led_current_power_consumption(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC currentPowerConsumption Sensor."""
    entity_id = "sensor.esi_led_currentPowerConsumption"
    entity_name = "esi_led CurrentPowerConsumption"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_led"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "189.15"


async def test_hmip_esi_led_energy_counter_usage_high_tariff(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test ESI-IEC ENERGY_COUNTER_USAGE_HIGH_TARIFF."""
    entity_id = "sensor.esi_led_energy_counter_usage_high_tariff"
    entity_name = "esi_led ENERGY_COUNTER_USAGE_HIGH_TARIFF"
    device_model = "HmIP-ESI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["esi_led"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "23825.748"


async def test_hmip_absolute_humidity_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test absolute humidity sensor (vaporAmount)."""
    entity_id = "sensor.elvshctv_absolute_humidity"
    entity_name = "elvshctv Absolute Humidity"
    device_model = "ELV-SH-CTH"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["elvshctv"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "6098"


async def test_hmip_absolute_humidity_sensor_invalid_value(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test absolute humidity sensor with invalid value for vaporAmount."""
    entity_id = "sensor.elvshctv_absolute_humidity"
    entity_name = "elvshctv Absolute Humidity"
    device_model = "ELV-SH-CTH"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["elvshctv"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    await async_manipulate_test_data(hass, hmip_device, "vaporAmount", None, 1)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == STATE_UNKNOWN
