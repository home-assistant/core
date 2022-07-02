"""The tests for the Scrape sensor platform."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.scrape.sensor import SCAN_INTERVAL

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MockRestData, init_integration, return_config

from tests.common import async_fire_time_changed

DOMAIN = "scrape"


async def test_scrape_sensor(hass: HomeAssistant) -> None:
    """Test Scrape sensor minimal."""
    config = {
        DOMAIN: [
            return_config(
                select=".current-version h1", name="HA version", remove_platform=True
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"


async def test_scrape_sensor_value_template(hass: HomeAssistant) -> None:
    """Test Scrape sensor with value template."""
    config = {
        DOMAIN: [
            return_config(
                select=".current-version h1",
                name="HA version",
                template="{{ value.split(':')[1] }}",
                remove_platform=True,
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "2021.12.10"


async def test_scrape_uom_and_classes(hass: HomeAssistant) -> None:
    """Test Scrape sensor for unit of measurement, device class and state class."""
    config = {
        DOMAIN: [
            return_config(
                select=".current-temp h3",
                name="Current Temp",
                template="{{ value.split(':')[1] }}",
                uom="°C",
                device_class="temperature",
                state_class="measurement",
                remove_platform=True,
            )
        ]
    }

    mocker = MockRestData("test_scrape_uom_and_classes")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_temp")
    assert state.state == "22.1"
    assert state.attributes[CONF_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert state.attributes[CONF_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[CONF_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_scrape_unique_id(hass: HomeAssistant) -> None:
    """Test Scrape sensor for unique id."""
    config = {
        "sensor": return_config(
            select=".current-temp h3",
            name="Current Temp",
            template="{{ value.split(':')[1] }}",
            unique_id="very_unique_id",
        )
    }

    mocker = MockRestData("test_scrape_uom_and_classes")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_temp")
    assert state.state == "22.1"

    registry = er.async_get(hass)
    entry = registry.async_get("sensor.current_temp")
    assert entry
    assert entry.unique_id == "very_unique_id"


async def test_scrape_sensor_authentication(hass: HomeAssistant) -> None:
    """Test Scrape sensor with authentication."""
    config = {
        DOMAIN: [
            return_config(
                select=".return",
                name="Auth page",
                username="user@secret.com",
                password="12345678",
                authentication="digest",
                remove_platform=True,
            ),
            return_config(
                select=".return",
                name="Auth page2",
                username="user@secret.com",
                password="12345678",
                remove_platform=True,
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor_authentication")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.auth_page")
    assert state.state == "secret text"
    state2 = hass.states.get("sensor.auth_page2")
    assert state2.state == "secret text"


async def test_scrape_sensor_no_data(hass: HomeAssistant) -> None:
    """Test Scrape sensor fails on no data."""
    config = {
        DOMAIN: return_config(
            select=".current-version h1", name="HA version", remove_platform=True
        )
    }

    mocker = MockRestData("test_scrape_sensor_no_data")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is None


async def test_scrape_sensor_no_data_refresh(hass: HomeAssistant) -> None:
    """Test Scrape sensor no data on refresh."""
    config = {
        DOMAIN: [
            return_config(
                select=".current-version h1", name="HA version", remove_platform=True
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state
    assert state.state == "Current Version: 2021.12.10"

    mocker.payload = "test_scrape_sensor_no_data"
    async_fire_time_changed(hass, datetime.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_scrape_sensor_attribute_and_tag(hass: HomeAssistant) -> None:
    """Test Scrape sensor with attribute and tag."""
    config = {
        DOMAIN: [
            return_config(
                select="div",
                name="HA class",
                index=1,
                attribute="class",
                remove_platform=True,
            ),
            return_config(select="template", name="HA template", remove_platform=True),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == "['links']"
    state2 = hass.states.get("sensor.ha_template")
    assert state2.state == "Trying to get"


async def test_scrape_sensor_errors(hass: HomeAssistant) -> None:
    """Test Scrape sensor handle errors."""
    config = {
        DOMAIN: [
            return_config(
                select="div",
                name="HA class",
                index=5,
                attribute="class",
                remove_platform=True,
            ),
            return_config(
                select="div",
                name="HA class2",
                attribute="classes",
                remove_platform=True,
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == STATE_UNKNOWN
    state2 = hass.states.get("sensor.ha_class2")
    assert state2.state == STATE_UNKNOWN


async def test_scrape_sensor_config_entry(hass: HomeAssistant) -> None:
    """Test Scrape sensor minimal."""
    await init_integration(
        hass,
        return_config(select=".current-version h1", name="HA version"),
        "test_scrape_sensor",
    )

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"


async def test_scrape_sensor_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Scrape sensor logs deprecated."""
    config = {"sensor": return_config(select=".current-version h1", name="HA version")}

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.scrape.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    assert "Loading Scrape via platform key has been deprecated" in caplog.text
