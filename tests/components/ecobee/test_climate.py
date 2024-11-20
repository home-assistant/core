"""The test for the Ecobee thermostat module."""

from http import HTTPStatus
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import const
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.ecobee.climate import (
    ATTR_PRESET_MODE,
    ATTR_SENSOR_LIST,
    PRESET_AWAY_INDEFINITELY,
    Thermostat,
)
from homeassistant.components.ecobee.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .common import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.ecobee"


@pytest.fixture
def ecobee_fixture():
    """Set up ecobee mock."""
    vals = {
        "name": "Ecobee",
        "modelNumber": "athenaSmart",
        "identifier": "abc",
        "program": {
            "climates": [
                {
                    "name": "Climate1",
                    "climateRef": "c1",
                    "sensors": [{"name": "Ecobee"}],
                },
                {
                    "name": "Climate2",
                    "climateRef": "c2",
                    "sensors": [{"name": "Ecobee"}],
                },
                {"name": "Away", "climateRef": "away", "sensors": [{"name": "Ecobee"}]},
                {"name": "Home", "climateRef": "home", "sensors": [{"name": "Ecobee"}]},
            ],
            "currentClimateRef": "c1",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 300,
            "actualHumidity": 15,
            "desiredHeat": 400,
            "desiredCool": 200,
            "desiredFanMode": "on",
        },
        "settings": {
            "hvacMode": "auto",
            "heatStages": 1,
            "coolStages": 1,
            "fanMinOnTime": 10,
            "heatCoolMinDelta": 50,
            "holdAction": "nextTransition",
        },
        "equipmentStatus": "fan",
        "events": [
            {
                "name": "Event1",
                "running": True,
                "type": "hold",
                "holdClimateRef": "c1",
                "startDate": "2017-02-02",
                "startTime": "11:00:00",
                "endDate": "2017-01-01",
                "endTime": "10:00:00",
            }
        ],
        "remoteSensors": [
            {
                "id": "ei:0",
                "name": "Ecobee",
            },
            {
                "id": "rs2:100",
                "name": "Remote Sensor 1",
            },
        ],
    }
    mock_ecobee = mock.Mock()
    mock_ecobee.get = mock.Mock(side_effect=vals.get)
    mock_ecobee.__getitem__ = mock.Mock(side_effect=vals.__getitem__)
    mock_ecobee.__setitem__ = mock.Mock(side_effect=vals.__setitem__)
    return mock_ecobee


@pytest.fixture(name="data")
def data_fixture(ecobee_fixture):
    """Set up data mock."""
    data = mock.Mock()
    data.ecobee.get_thermostat.return_value = ecobee_fixture
    return data


@pytest.fixture(name="thermostat")
def thermostat_fixture(data, hass: HomeAssistant):
    """Set up ecobee thermostat object."""
    thermostat = data.ecobee.get_thermostat(1)
    return Thermostat(data, 1, thermostat, hass)


async def test_name(thermostat) -> None:
    """Test name property."""
    assert thermostat.device_info["name"] == "Ecobee"


async def test_aux_heat_not_supported_by_default(hass: HomeAssistant) -> None:
    """Default setup should not support Aux heat."""
    await setup_platform(hass, const.Platform.CLIMATE)
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_HUMIDITY
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )


async def test_current_temperature(ecobee_fixture, thermostat) -> None:
    """Test current temperature."""
    assert thermostat.current_temperature == 30
    ecobee_fixture["runtime"]["actualTemperature"] = HTTPStatus.NOT_FOUND
    assert thermostat.current_temperature == 40.4


async def test_target_temperature_low(ecobee_fixture, thermostat) -> None:
    """Test target low temperature."""
    assert thermostat.target_temperature_low == 40
    ecobee_fixture["runtime"]["desiredHeat"] = 502
    assert thermostat.target_temperature_low == 50.2


async def test_target_temperature_high(ecobee_fixture, thermostat) -> None:
    """Test target high temperature."""
    assert thermostat.target_temperature_high == 20
    ecobee_fixture["runtime"]["desiredCool"] = 679
    assert thermostat.target_temperature_high == 67.9


async def test_target_temperature(ecobee_fixture, thermostat) -> None:
    """Test target temperature."""
    assert thermostat.target_temperature is None
    ecobee_fixture["settings"]["hvacMode"] = "heat"
    assert thermostat.target_temperature == 40
    ecobee_fixture["settings"]["hvacMode"] = "cool"
    assert thermostat.target_temperature == 20
    ecobee_fixture["settings"]["hvacMode"] = "auxHeatOnly"
    assert thermostat.target_temperature == 40
    ecobee_fixture["settings"]["hvacMode"] = "off"
    assert thermostat.target_temperature is None


async def test_desired_fan_mode(ecobee_fixture, thermostat) -> None:
    """Test desired fan mode property."""
    assert thermostat.fan_mode == "on"
    ecobee_fixture["runtime"]["desiredFanMode"] = "auto"
    assert thermostat.fan_mode == "auto"


async def test_fan(ecobee_fixture, thermostat) -> None:
    """Test fan property."""
    assert thermostat.fan == const.STATE_ON
    ecobee_fixture["equipmentStatus"] = ""
    assert thermostat.fan == STATE_OFF
    ecobee_fixture["equipmentStatus"] = "heatPump, heatPump2"
    assert thermostat.fan == STATE_OFF


async def test_hvac_mode(ecobee_fixture, thermostat) -> None:
    """Test current operation property."""
    assert thermostat.hvac_mode == "heat_cool"
    ecobee_fixture["settings"]["hvacMode"] = "heat"
    assert thermostat.hvac_mode == "heat"
    ecobee_fixture["settings"]["hvacMode"] = "cool"
    assert thermostat.hvac_mode == "cool"
    ecobee_fixture["settings"]["hvacMode"] = "auxHeatOnly"
    assert thermostat.hvac_mode == "heat"
    ecobee_fixture["settings"]["hvacMode"] = "off"
    assert thermostat.hvac_mode == "off"


async def test_hvac_modes(thermostat) -> None:
    """Test operation list property."""
    assert thermostat.hvac_modes == ["heat_cool", "heat", "cool", "off"]


async def test_hvac_mode2(ecobee_fixture, thermostat) -> None:
    """Test operation mode property."""
    assert thermostat.hvac_mode == "heat_cool"
    ecobee_fixture["settings"]["hvacMode"] = "heat"
    assert thermostat.hvac_mode == "heat"


async def test_extra_state_attributes(ecobee_fixture, thermostat) -> None:
    """Test device state attributes property."""
    ecobee_fixture["equipmentStatus"] = "heatPump2"
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate1",
        "fan_min_on_time": 10,
        "equipment_running": "heatPump2",
        "available_sensors": [],
        "active_sensors": [],
    }

    ecobee_fixture["equipmentStatus"] = "auxHeat2"
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate1",
        "fan_min_on_time": 10,
        "equipment_running": "auxHeat2",
        "available_sensors": [],
        "active_sensors": [],
    }

    ecobee_fixture["equipmentStatus"] = "compCool1"
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate1",
        "fan_min_on_time": 10,
        "equipment_running": "compCool1",
        "available_sensors": [],
        "active_sensors": [],
    }
    ecobee_fixture["equipmentStatus"] = ""
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate1",
        "fan_min_on_time": 10,
        "equipment_running": "",
        "available_sensors": [],
        "active_sensors": [],
    }

    ecobee_fixture["equipmentStatus"] = "Unknown"
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate1",
        "fan_min_on_time": 10,
        "equipment_running": "Unknown",
        "available_sensors": [],
        "active_sensors": [],
    }

    ecobee_fixture["program"]["currentClimateRef"] = "c2"
    assert thermostat.extra_state_attributes == {
        "fan": "off",
        "climate_mode": "Climate2",
        "fan_min_on_time": 10,
        "equipment_running": "Unknown",
        "available_sensors": [],
        "active_sensors": [],
    }


async def test_set_temperature(ecobee_fixture, thermostat, data) -> None:
    """Test set temperature."""
    # Auto -> Auto
    data.reset_mock()
    thermostat.set_temperature(target_temp_low=20, target_temp_high=30)
    data.ecobee.set_hold_temp.assert_has_calls(
        [mock.call(1, 30, 20, "nextTransition", None)]
    )

    # Auto -> Hold
    data.reset_mock()
    thermostat.set_temperature(temperature=20)
    data.ecobee.set_hold_temp.assert_has_calls(
        [mock.call(1, 25, 15, "nextTransition", None)]
    )

    # Cool -> Hold
    data.reset_mock()
    ecobee_fixture["settings"]["hvacMode"] = "cool"
    thermostat.set_temperature(temperature=20.5)
    data.ecobee.set_hold_temp.assert_has_calls(
        [mock.call(1, 20.5, 20.5, "nextTransition", None)]
    )

    # Heat -> Hold
    data.reset_mock()
    ecobee_fixture["settings"]["hvacMode"] = "heat"
    thermostat.set_temperature(temperature=20)
    data.ecobee.set_hold_temp.assert_has_calls(
        [mock.call(1, 20, 20, "nextTransition", None)]
    )

    # Heat -> Auto
    data.reset_mock()
    ecobee_fixture["settings"]["hvacMode"] = "heat"
    thermostat.set_temperature(target_temp_low=20, target_temp_high=30)
    assert not data.ecobee.set_hold_temp.called


async def test_set_hvac_mode(thermostat, data) -> None:
    """Test operation mode setter."""
    data.reset_mock()
    thermostat.set_hvac_mode("heat_cool")
    data.ecobee.set_hvac_mode.assert_has_calls([mock.call(1, "auto")])
    data.reset_mock()
    thermostat.set_hvac_mode("heat")
    data.ecobee.set_hvac_mode.assert_has_calls([mock.call(1, "heat")])


async def test_set_fan_min_on_time(thermostat, data) -> None:
    """Test fan min on time setter."""
    data.reset_mock()
    thermostat.set_fan_min_on_time(15)
    data.ecobee.set_fan_min_on_time.assert_has_calls([mock.call(1, 15)])
    data.reset_mock()
    thermostat.set_fan_min_on_time(20)
    data.ecobee.set_fan_min_on_time.assert_has_calls([mock.call(1, 20)])


async def test_resume_program(thermostat, data) -> None:
    """Test resume program."""
    # False
    data.reset_mock()
    thermostat.resume_program(False)
    data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])
    data.reset_mock()
    thermostat.resume_program(None)
    data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])
    data.reset_mock()
    thermostat.resume_program(0)
    data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])

    # True
    data.reset_mock()
    thermostat.resume_program(True)
    data.ecobee.resume_program.assert_has_calls([mock.call(1, "true")])
    data.reset_mock()
    thermostat.resume_program(1)
    data.ecobee.resume_program.assert_has_calls([mock.call(1, "true")])


async def test_hold_preference(ecobee_fixture, thermostat) -> None:
    """Test hold preference."""
    ecobee_fixture["settings"]["holdAction"] = "indefinite"
    assert thermostat.hold_preference() == "indefinite"
    for action in ("useEndTime2hour", "useEndTime4hour"):
        ecobee_fixture["settings"]["holdAction"] = action
        assert thermostat.hold_preference() == "holdHours"
    for action in ("nextPeriod", "askMe"):
        ecobee_fixture["settings"]["holdAction"] = action
        assert thermostat.hold_preference() == "nextTransition"


def test_hold_hours(ecobee_fixture, thermostat) -> None:
    """Test hold hours preference."""
    ecobee_fixture["settings"]["holdAction"] = "useEndTime2hour"
    assert thermostat.hold_hours() == 2
    ecobee_fixture["settings"]["holdAction"] = "useEndTime4hour"
    assert thermostat.hold_hours() == 4
    for action in ("nextPeriod", "indefinite", "askMe"):
        ecobee_fixture["settings"]["holdAction"] = action
        assert thermostat.hold_hours() is None


async def test_set_fan_mode_on(thermostat, data) -> None:
    """Test set fan mode to on."""
    data.reset_mock()
    thermostat.set_fan_mode("on")
    data.ecobee.set_fan_mode.assert_has_calls(
        [mock.call(1, "on", "nextTransition", holdHours=None)]
    )


async def test_set_fan_mode_auto(thermostat, data) -> None:
    """Test set fan mode to auto."""
    data.reset_mock()
    thermostat.set_fan_mode("auto")
    data.ecobee.set_fan_mode.assert_has_calls(
        [mock.call(1, "auto", "nextTransition", holdHours=None)]
    )


async def test_preset_indefinite_away(ecobee_fixture, thermostat) -> None:
    """Test indefinite away showing correctly, and not as temporary away."""
    ecobee_fixture["program"]["currentClimateRef"] = "away"
    ecobee_fixture["events"][0]["holdClimateRef"] = "away"
    assert thermostat.preset_mode == "away"

    ecobee_fixture["events"][0]["endDate"] = "2999-01-01"
    assert thermostat.preset_mode == PRESET_AWAY_INDEFINITELY


async def test_set_preset_mode(ecobee_fixture, thermostat, data) -> None:
    """Test set preset mode."""
    # Set a preset provided by ecobee.
    data.reset_mock()
    thermostat.set_preset_mode("Climate2")
    data.ecobee.set_climate_hold.assert_has_calls(
        [mock.call(1, "c2", thermostat.hold_preference(), thermostat.hold_hours())]
    )

    # Set the indefinite away preset provided by this integration.
    data.reset_mock()
    thermostat.set_preset_mode(PRESET_AWAY_INDEFINITELY)
    data.ecobee.set_climate_hold.assert_has_calls(
        [mock.call(1, "away", "indefinite", thermostat.hold_hours())]
    )


async def test_remote_sensors(hass: HomeAssistant) -> None:
    """Test remote sensors."""
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    platform = hass.data[const.Platform.CLIMATE].entities
    for entity in platform:
        if entity.entity_id == "climate.ecobee":
            thermostat = entity
            break

    assert thermostat is not None
    remote_sensors = thermostat.remote_sensors

    assert sorted(remote_sensors) == sorted(["ecobee", "Remote Sensor 1"])


async def test_remote_sensor_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test remote sensor devices."""
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    freezer.tick(100)
    async_fire_time_changed(hass)
    state = hass.states.get(ENTITY_ID)
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.values():
        if device.name == "Remote Sensor 1":
            remote_sensor_1_id = device.id
        if device.name == "ecobee":
            ecobee_id = device.id
    assert sorted(state.attributes.get("available_sensors")) == sorted(
        [f"Remote Sensor 1 ({remote_sensor_1_id})", f"ecobee ({ecobee_id})"]
    )


async def test_active_sensors_in_preset_mode(hass: HomeAssistant) -> None:
    """Test active sensors in preset mode property."""
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    platform = hass.data[const.Platform.CLIMATE].entities
    for entity in platform:
        if entity.entity_id == "climate.ecobee":
            thermostat = entity
            break

    assert thermostat is not None
    remote_sensors = thermostat.active_sensors_in_preset_mode

    assert sorted(remote_sensors) == sorted(["ecobee"])


async def test_active_sensor_devices_in_preset_mode(hass: HomeAssistant) -> None:
    """Test active sensor devices in preset mode."""
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    state = hass.states.get(ENTITY_ID)

    assert state.attributes.get("active_sensors") == ["ecobee"]


async def test_remote_sensor_ids_names(hass: HomeAssistant) -> None:
    """Test getting ids and names_by_user for thermostat."""
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    platform = hass.data[const.Platform.CLIMATE].entities
    for entity in platform:
        if entity.entity_id == "climate.ecobee":
            thermostat = entity
            break

    assert thermostat is not None

    remote_sensor_ids_names = thermostat.remote_sensor_ids_names
    for id_name in remote_sensor_ids_names:
        assert id_name.get("id") is not None

    name_by_user_list = [item["name_by_user"] for item in remote_sensor_ids_names]
    assert sorted(name_by_user_list) == sorted(["Remote Sensor 1", "ecobee"])


async def test_set_sensors_used_in_climate(hass: HomeAssistant) -> None:
    """Test set sensors used in climate."""
    # Get device_id of remote sensor from the device registry.
    await setup_platform(hass, [const.Platform.CLIMATE, const.Platform.SENSOR])
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.values():
        if device.name == "Remote Sensor 1":
            remote_sensor_1_id = device.id
        if device.name == "ecobee":
            ecobee_id = device.id
        if device.name == "Remote Sensor 2":
            remote_sensor_2_id = device.id

    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_from_other_integration = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "unique")}
    )

    # Test that the function call works in its entirety.
    with mock.patch("pyecobee.Ecobee.update_climate_sensors") as mock_sensors:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "Climate1",
                ATTR_SENSOR_LIST: [remote_sensor_1_id],
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_sensors.assert_called_once_with(0, "Climate1", sensor_ids=["rs:100"])

    # Update sensors without preset mode.
    with mock.patch("pyecobee.Ecobee.update_climate_sensors") as mock_sensors:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_SENSOR_LIST: [remote_sensor_1_id],
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        # `temp` is the preset running because of a hold.
        mock_sensors.assert_called_once_with(0, "temp", sensor_ids=["rs:100"])

    # Check that sensors are not updated when the sent sensors are the currently set sensors.
    with mock.patch("pyecobee.Ecobee.update_climate_sensors") as mock_sensors:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "Climate1",
                ATTR_SENSOR_LIST: [ecobee_id],
            },
            blocking=True,
        )
        mock_sensors.assert_not_called()

    # Error raised because invalid climate name.
    with pytest.raises(ServiceValidationError) as execinfo:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "InvalidClimate",
                ATTR_SENSOR_LIST: [remote_sensor_1_id],
            },
            blocking=True,
        )
    assert execinfo.value.translation_domain == "ecobee"
    assert execinfo.value.translation_key == "invalid_preset"

    ## Error raised because invalid sensor.
    with pytest.raises(ServiceValidationError) as execinfo:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "Climate1",
                ATTR_SENSOR_LIST: ["abcd"],
            },
            blocking=True,
        )
    assert execinfo.value.translation_domain == "ecobee"
    assert execinfo.value.translation_key == "invalid_sensor"

    ## Error raised because sensor not available on device.
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "Climate1",
                ATTR_SENSOR_LIST: [remote_sensor_2_id],
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError) as execinfo:
        await hass.services.async_call(
            DOMAIN,
            "set_sensors_used_in_climate",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: "Climate1",
                ATTR_SENSOR_LIST: [
                    remote_sensor_1_id,
                    device_from_other_integration.id,
                ],
            },
            blocking=True,
        )
    assert execinfo.value.translation_domain == "ecobee"
    assert execinfo.value.translation_key == "sensor_lookup_failed"
