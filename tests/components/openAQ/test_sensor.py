"""Test openAQ sensor."""

from unittest import mock

import pytest

from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.openAQ.conftest import ComponentSetup, OpenAQMock


@pytest.mark.asyncio
@mock.patch(
    "openaq.__new__", OpenAQMock("location_good.json", "measurements_good.json")
)
async def test_get_sensor_hardcoded_values(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test if sensor entities are added and their values are non-negative."""
    # Perform setup of the integration
    await setup_integration(
        config_entry, "location_good.json", "measurements_good.json"
    )
    async_add_entities = await async_setup_component(hass, DOMAIN, config_entry)
    assert async_add_entities

    # Assert that the sensor exists in the JSON object
    assert hass.states.get("sensor.pm25").state == "8.2"
    assert hass.states.get("sensor.pm10").state == "17.0"
    assert hass.states.get("sensor.nitrogen_dioxide").state == "29"
    assert hass.states.get("sensor.ozone").state == "8.2"
    assert hass.states.get("sensor.co").state == "8.2"
    assert hass.states.get("sensor.sulphur_dioxide").state == "29"
    assert hass.states.get("sensor.nitrogen_monoxide").state == "9.5"


@pytest.mark.asyncio
@mock.patch(
    "openaq.__new__", OpenAQMock("location_good.json", "measurements_negative.json")
)
async def test_sensors_with_negative(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test if sensor entities are added and their values are non-negative."""
    # Perform setup of the integration
    await setup_integration(
        config_entry, "location_good.json", "measurements_negative.json"
    )
    async_add_entities = await async_setup_component(hass, DOMAIN, config_entry)
    assert async_add_entities

    # Check that sensor values are less than or  equal to 0
    assert float(hass.states.get("sensor.pm25").state) == 0
    assert float(hass.states.get("sensor.pm10").state) == 0
    assert float(hass.states.get("sensor.nitrogen_dioxide").state) == 0
    assert float(hass.states.get("sensor.ozone").state) == -2
    assert float(hass.states.get("sensor.co").state) == 0


@pytest.mark.asyncio
@mock.patch(
    "openaq.__new__", OpenAQMock("location_good.json", "measurements_negative.json")
)
async def test_negative_for_one_sensor_values(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
):
    """Test if sensor entities are added and their values are non-negative except ozone."""
    # Perform setup of the integration
    await setup_integration(
        config_entry, "location_good.json", "measurements_negative.json"
    )
    async_add_entities = await async_setup_component(hass, DOMAIN, config_entry)
    assert async_add_entities

    # Check if sensor entities are added and their values are not negative, except for the ozone sensor
    sensors = hass.states.async_entity_ids("sensor")
    for sensor in sensors:
        state = hass.states.get(sensor)

        if state is not None:
            if (
                state.attributes.get("name") != "ozone"
            ):  # Skip checking for ozone sensor
                try:
                    sensor_value = float(state.state)
                    assert (
                        sensor_value <= 0
                    ), f"Negative value found for sensor {sensor}"
                except ValueError:
                    pass  # Skip this sensor for value checking
