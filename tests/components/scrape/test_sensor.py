"""The tests for the Scrape sensor platform."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.sensor.const import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from . import MockRestData, return_config

DOMAIN = "scrape"


async def test_scrape_sensor(hass: HomeAssistant) -> None:
    """Test Scrape sensor minimal."""
    config = {"sensor": return_config(select=".current-version h1", name="HA version")}

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"


async def test_scrape_sensor_value_template(hass: HomeAssistant) -> None:
    """Test Scrape sensor with value template."""
    config = {
        "sensor": return_config(
            select=".current-version h1",
            name="HA version",
            template="{{ value.split(':')[1] }}",
        )
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "2021.12.10"


async def test_scrape_uom_and_classes(hass: HomeAssistant) -> None:
    """Test Scrape sensor for unit of measurement, device class and state class."""
    config = {
        "sensor": return_config(
            select=".current-temp h3",
            name="Current Temp",
            template="{{ value.split(':')[1] }}",
            uom="°C",
            device_class="temperature",
            state_class="measurement",
        )
    }

    mocker = MockRestData("test_scrape_uom_and_classes")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_temp")
    assert state.state == "22.1"
    assert state.attributes[CONF_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert state.attributes[CONF_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[CONF_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_scrape_sensor_authentication(hass: HomeAssistant) -> None:
    """Test Scrape sensor with authentication."""
    config = {
        "sensor": [
            return_config(
                select=".return",
                name="Auth page",
                username="user@secret.com",
                password="12345678",
                authentication="digest",
            ),
            return_config(
                select=".return",
                name="Auth page2",
                username="user@secret.com",
                password="12345678",
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor_authentication")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.auth_page")
    assert state.state == "secret text"
    state2 = hass.states.get("sensor.auth_page2")
    assert state2.state == "secret text"


async def test_scrape_sensor_no_data(hass: HomeAssistant) -> None:
    """Test Scrape sensor fails on no data."""
    config = {"sensor": return_config(select=".current-version h1", name="HA version")}

    mocker = MockRestData("test_scrape_sensor_no_data")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is None


async def test_scrape_sensor_no_data_refresh(hass: HomeAssistant) -> None:
    """Test Scrape sensor no data on refresh."""
    config = {"sensor": return_config(select=".current-version h1", name="HA version")}

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state
    assert state.state == "Current Version: 2021.12.10"

    mocker.data = None
    await async_update_entity(hass, "sensor.ha_version")

    assert mocker.data is None
    assert state is not None
    assert state.state == "Current Version: 2021.12.10"


async def test_scrape_sensor_attribute_and_tag(hass: HomeAssistant) -> None:
    """Test Scrape sensor with attribute and tag."""
    config = {
        "sensor": [
            return_config(select="div", name="HA class", index=1, attribute="class"),
            return_config(select="template", name="HA template"),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == "['links']"
    state2 = hass.states.get("sensor.ha_template")
    assert state2.state == "Trying to get"


async def test_scrape_sensor_errors(hass: HomeAssistant) -> None:
    """Test Scrape sensor handle errors."""
    config = {
        "sensor": [
            return_config(select="div", name="HA class", index=5, attribute="class"),
            return_config(select="div", name="HA class2", attribute="classes"),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == STATE_UNKNOWN
    state2 = hass.states.get("sensor.ha_class2")
    assert state2.state == STATE_UNKNOWN
