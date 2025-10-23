"""Test the DayBetter Services sensor platform."""

from unittest.mock import patch

from homeassistant.components.daybetter_services.const import DOMAIN
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[
                {
                    "deviceId": "test_device_1",
                    "deviceName": "test_sensor",
                    "deviceGroupName": "Test Group",
                    "deviceMoldPid": "pid1",
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={"sensor": "pid1"},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[
                {
                    "deviceName": "test_sensor",
                    "type": 5,
                    "temp": 225,  # Raw value, will be divided by 10 to get 22.5
                    "humi": 650,  # Raw value, will be divided by 10 to get 65.0
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check that sensors were created
        # Entity IDs are based on device group and name
        states = hass.states.async_all()
        temp_sensors = [s for s in states if "temperature" in s.entity_id]
        humi_sensors = [s for s in states if "humidity" in s.entity_id]

        assert len(temp_sensors) == 1
        assert len(humi_sensors) == 1
        assert temp_sensors[0].state == "22.5"
        assert humi_sensors[0].state == "65.0"


async def test_sensor_attributes(hass: HomeAssistant) -> None:
    """Test sensor attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[
                {
                    "deviceId": "test_device_1",
                    "deviceName": "test_sensor",
                    "deviceGroupName": "Test Group",
                    "deviceMoldPid": "pid1",
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={"sensor": "pid1"},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[
                {
                    "deviceName": "test_sensor",
                    "type": 5,
                    "temp": 225,  # Raw value, will be divided by 10 to get 22.5
                    "humi": 650,  # Raw value, will be divided by 10 to get 65.0
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        states = hass.states.async_all()
        temp_sensors = [s for s in states if "temperature" in s.entity_id]
        humi_sensors = [s for s in states if "humidity" in s.entity_id]

        # Check temperature sensor attributes
        assert len(temp_sensors) == 1
        temp_sensor = temp_sensors[0]
        assert (
            temp_sensor.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
        )
        assert temp_sensor.attributes["device_class"] == "temperature"
        assert temp_sensor.attributes["state_class"] == "measurement"

        # Check humidity sensor attributes
        assert len(humi_sensors) == 1
        humidity_sensor = humi_sensors[0]
        assert humidity_sensor.attributes["unit_of_measurement"] == PERCENTAGE
        assert humidity_sensor.attributes["device_class"] == "humidity"
        assert humidity_sensor.attributes["state_class"] == "measurement"


async def test_sensor_no_devices(hass: HomeAssistant) -> None:
    """Test sensor setup with no devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # No sensors should be created
        states = hass.states.async_all()
        sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]
        assert len(sensor_states) == 0


async def test_sensor_wrong_device_type(hass: HomeAssistant) -> None:
    """Test sensor setup with wrong device type (non-sensor PID)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[
                {
                    "deviceId": "test_device_1",
                    "deviceName": "test_device",
                    "deviceGroupName": "Test Group",
                    "deviceMoldPid": "light_pid1",  # Light PID, not sensor
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={"light": "light_pid1", "sensor": "sensor_pid1"},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # No sensors should be created for non-sensor devices
        states = hass.states.async_all()
        sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]
        assert len(sensor_states) == 0


async def test_sensor_update(hass: HomeAssistant) -> None:
    """Test sensor data update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    mock_devices = [
        {
            "deviceId": "test_device_1",
            "deviceName": "test_sensor",
            "deviceGroupName": "Test Group",
            "deviceMoldPid": "pid1",
        }
    ]

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={"sensor": "pid1"},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[
                {
                    "deviceName": "test_sensor",
                    "type": 5,
                    "temp": 225,  # Raw value, will be divided by 10 to get 22.5
                    "humi": 650,  # Raw value, will be divided by 10 to get 65.0
                }
            ],
        ) as mock_fetch_statuses,
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Initial values
        states = hass.states.async_all()
        temp_sensors = [s for s in states if "temperature" in s.entity_id]
        assert len(temp_sensors) == 1
        assert temp_sensors[0].state == "22.5"

        # Update with new values
        mock_fetch_statuses.return_value = [
            {
                "deviceName": "test_sensor",
                "type": 5,
                "temp": 250,  # Raw value, will be divided by 10 to get 25.0
                "humi": 700,  # Raw value, will be divided by 10 to get 70.0
            }
        ]

        # Trigger coordinator refresh
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Check updated values
        states = hass.states.async_all()
        temp_sensors = [s for s in states if "temperature" in s.entity_id]
        humi_sensors = [s for s in states if "humidity" in s.entity_id]
        assert len(temp_sensors) == 1
        assert len(humi_sensors) == 1
        assert temp_sensors[0].state == "25.0"
        assert humi_sensors[0].state == "70.0"
