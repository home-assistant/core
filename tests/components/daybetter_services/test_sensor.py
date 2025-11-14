"""Test the DayBetter Services sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.daybetter_services.const import DOMAIN
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[
                {
                    "deviceId": "test_device_1",
                    "deviceName": "test_sensor",
                    "deviceGroupName": "Test Group",
                    "deviceMoldPid": "pid1",
                    "temp": 225,  # Raw value, will be divided by 10 to get 22.5
                    "humi": 650,  # Raw value, will be divided by 10 to get 65.0
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        temp_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_temperature"
        )
        humi_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_humidity"
        )

        assert temp_entity_id is not None
        assert humi_entity_id is not None

        temp_state = hass.states.get(temp_entity_id)
        humi_state = hass.states.get(humi_entity_id)

        assert temp_state is not None
        assert humi_state is not None
        assert temp_state.state == "22.5"
        assert humi_state.state == "65.0"


async def test_sensor_attributes(hass: HomeAssistant) -> None:
    """Test sensor attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[
                {
                    "deviceId": "test_device_1",
                    "deviceName": "test_sensor",
                    "deviceGroupName": "Test Group",
                    "deviceMoldPid": "pid1",
                    "temp": 225,  # Raw value, will be divided by 10 to get 22.5
                    "humi": 650,  # Raw value, will be divided by 10 to get 65.0
                }
            ],
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        temp_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_temperature"
        )
        humi_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_humidity"
        )

        assert temp_entity_id is not None
        assert humi_entity_id is not None

        temp_sensor_state = hass.states.get(temp_entity_id)
        humidity_sensor_state = hass.states.get(humi_entity_id)

        assert temp_sensor_state is not None
        assert humidity_sensor_state is not None
        assert (
            temp_sensor_state.attributes["unit_of_measurement"]
            == UnitOfTemperature.CELSIUS
        )
        assert temp_sensor_state.attributes["device_class"] == "temperature"
        assert temp_sensor_state.attributes["state_class"] == "measurement"

        assert humidity_sensor_state.attributes["unit_of_measurement"] == PERCENTAGE
        assert humidity_sensor_state.attributes["device_class"] == "humidity"
        assert humidity_sensor_state.attributes["state_class"] == "measurement"


async def test_sensor_no_devices(hass: HomeAssistant) -> None:
    """Test sensor setup with no devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert not hass.states.async_entity_ids("sensor")


async def test_sensor_wrong_device_type(hass: HomeAssistant) -> None:
    """Test sensor setup with wrong device type (non-sensor PID)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[],  # Library filters out non-sensor devices
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert not hass.states.async_entity_ids("sensor")


async def test_sensor_update(hass: HomeAssistant) -> None:
    """Test sensor data update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            side_effect=[
                [
                    {
                        "deviceId": "test_device_1",
                        "deviceName": "test_sensor",
                        "deviceGroupName": "Test Group",
                        "deviceMoldPid": "pid1",
                        "temp": 225,
                        "humi": 650,
                    }
                ],
                [
                    {
                        "deviceId": "test_device_1",
                        "deviceName": "test_sensor",
                        "deviceGroupName": "Test Group",
                        "deviceMoldPid": "pid1",
                        "type": 5,
                        "temp": 250,
                        "humi": 700,
                    }
                ],
            ],
        ) as mock_fetch,
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        temp_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_temperature"
        )
        humi_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test_device_1_humidity"
        )

        assert temp_entity_id is not None
        assert humi_entity_id is not None

        temp_state = hass.states.get(temp_entity_id)
        assert temp_state is not None
        assert temp_state.state == "22.5"

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=300),
        )
        await hass.async_block_till_done()

        updated_temp_state = hass.states.get(temp_entity_id)
        updated_humi_state = hass.states.get(humi_entity_id)

        assert updated_temp_state is not None
        assert updated_humi_state is not None
        assert updated_temp_state.state == "25.0"
        assert updated_humi_state.state == "70.0"
        assert mock_fetch.call_count >= 2
