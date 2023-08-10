"""The tests for the Scrape sensor platform."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.scrape.const import (
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template_entity import CONF_AVAILABILITY, CONF_PICTURE
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MockRestData, return_integration_config

from tests.common import MockConfigEntry, async_fire_time_changed

DOMAIN = "scrape"


async def test_scrape_sensor(hass: HomeAssistant) -> None:
    """Test Scrape sensor minimal."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[{"select": ".current-version h1", "name": "HA version"}]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
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
            return_integration_config(
                sensors=[
                    {
                        "select": ".current-version h1",
                        "name": "HA version",
                        "value_template": "{{ value.split(':')[1] }}",
                    }
                ]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
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
            return_integration_config(
                sensors=[
                    {
                        "select": ".current-temp h3",
                        "name": "Current Temp",
                        "value_template": "{{ value.split(':')[1] }}",
                        "unit_of_measurement": "°C",
                        "device_class": "temperature",
                        "state_class": "measurement",
                    }
                ]
            )
        ]
    }

    mocker = MockRestData("test_scrape_uom_and_classes")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_temp")
    assert state.state == "22.1"
    assert state.attributes[CONF_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[CONF_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[CONF_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_scrape_unique_id(hass: HomeAssistant) -> None:
    """Test Scrape sensor for unique id."""
    config = {
        DOMAIN: return_integration_config(
            sensors=[
                {
                    "select": ".current-temp h3",
                    "name": "Current Temp",
                    "value_template": "{{ value.split(':')[1] }}",
                    "unique_id": "very_unique_id",
                }
            ]
        )
    }

    mocker = MockRestData("test_scrape_uom_and_classes")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
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
            return_integration_config(
                authentication="digest",
                username="user@secret.com",
                password="12345678",
                sensors=[
                    {
                        "select": ".return",
                        "name": "Auth page",
                    },
                ],
            ),
            return_integration_config(
                username="user@secret.com",
                password="12345678",
                sensors=[
                    {
                        "select": ".return",
                        "name": "Auth page2",
                    },
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor_authentication")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.auth_page")
    assert state.state == "secret text"
    state2 = hass.states.get("sensor.auth_page2")
    assert state2.state == "secret text"


async def test_scrape_sensor_no_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Scrape sensor fails on no data."""
    config = {
        DOMAIN: return_integration_config(
            sensors=[{"select": ".current-version h1", "name": "HA version"}]
        )
    }

    mocker = MockRestData("test_scrape_sensor_no_data")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is None

    assert "Platform scrape not ready yet" in caplog.text


async def test_scrape_sensor_no_data_refresh(hass: HomeAssistant) -> None:
    """Test Scrape sensor no data on refresh."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[{"select": ".current-version h1", "name": "HA version"}]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.ha_version")
        assert state
        assert state.state == "Current Version: 2021.12.10"

        mocker.payload = "test_scrape_sensor_no_data"
        async_fire_time_changed(hass, datetime.utcnow() + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_scrape_sensor_attribute_and_tag(hass: HomeAssistant) -> None:
    """Test Scrape sensor with attribute and tag."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "index": 1,
                        "select": "div",
                        "name": "HA class",
                        "attribute": "class",
                    },
                    {"select": "template", "name": "HA template"},
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == "['links']"
    state2 = hass.states.get("sensor.ha_template")
    assert state2.state == "Trying to get"


async def test_scrape_sensor_device_date(hass: HomeAssistant) -> None:
    """Test Scrape sensor with a device of type DATE."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "select": ".release-date",
                        "name": "HA Date",
                        "device_class": "date",
                        "value_template": "{{ strptime(value, '%B %d, %Y').strftime('%Y-%m-%d') }}",
                    }
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_date")
    assert state.state == "2022-01-17"


async def test_scrape_sensor_device_date_errors(hass: HomeAssistant) -> None:
    """Test Scrape sensor with a device of type DATE."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "select": ".current-version h1",
                        "name": "HA Date",
                        "device_class": "date",
                    }
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_date")
    assert state.state == STATE_UNKNOWN


async def test_scrape_sensor_device_timestamp(hass: HomeAssistant) -> None:
    """Test Scrape sensor with a device of type TIMESTAMP."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "select": ".utc-time",
                        "name": "HA Timestamp",
                        "device_class": "timestamp",
                    }
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_timestamp")
    assert state.state == "2022-12-22T13:15:30+00:00"


async def test_scrape_sensor_device_timestamp_error(hass: HomeAssistant) -> None:
    """Test Scrape sensor with a device of type TIMESTAMP."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "select": ".current-time",
                        "name": "HA Timestamp",
                        "device_class": "timestamp",
                    }
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_timestamp")
    assert state.state == STATE_UNKNOWN


async def test_scrape_sensor_errors(hass: HomeAssistant) -> None:
    """Test Scrape sensor handle errors."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "index": 5,
                        "select": "div",
                        "name": "HA class",
                        "attribute": "class",
                    },
                    {
                        "select": "div",
                        "name": "HA class2",
                        "attribute": "classes",
                    },
                ],
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_class")
    assert state.state == STATE_UNKNOWN
    state2 = hass.states.get("sensor.ha_class2")
    assert state2.state == STATE_UNKNOWN


async def test_scrape_sensor_unique_id(hass: HomeAssistant) -> None:
    """Test Scrape sensor with unique_id."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        "select": ".current-version h1",
                        "name": "HA version",
                        "unique_id": "ha_version_unique_id",
                    }
                ]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.ha_version")

    assert entity.unique_id == "ha_version_unique_id"


async def test_setup_config_entry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test setup from config entry."""

    state = hass.states.get("sensor.current_version")
    assert state.state == "Current Version: 2021.12.10"

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.current_version")

    assert entity.unique_id == "3699ef88-69e6-11ed-a1eb-0242ac120002"


async def test_templates_with_yaml(hass: HomeAssistant) -> None:
    """Test the Scrape sensor from yaml config with templates."""

    hass.states.async_set("sensor.input1", "on")
    hass.states.async_set("sensor.input2", "on")
    await hass.async_block_till_done()

    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[
                    {
                        CONF_NAME: "Get values with template",
                        CONF_SELECT: ".current-version h1",
                        CONF_INDEX: 0,
                        CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
                        CONF_ICON: '{% if states("sensor.input1")=="on" %} mdi:on {% else %} mdi:off {% endif %}',
                        CONF_PICTURE: '{% if states("sensor.input1")=="on" %} /local/picture1.jpg {% else %} /local/picture2.jpg {% endif %}',
                        CONF_AVAILABILITY: '{{ states("sensor.input2")=="on" }}',
                    }
                ]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "Current Version: 2021.12.10"
    assert state.attributes[CONF_ICON] == "mdi:on"
    assert state.attributes["entity_picture"] == "/local/picture1.jpg"

    hass.states.async_set("sensor.input1", "off")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=10),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "Current Version: 2021.12.10"
    assert state.attributes[CONF_ICON] == "mdi:off"
    assert state.attributes["entity_picture"] == "/local/picture2.jpg"

    hass.states.async_set("sensor.input2", "off")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=20),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.input1", "on")
    hass.states.async_set("sensor.input2", "on")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=30),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "Current Version: 2021.12.10"
    assert state.attributes[CONF_ICON] == "mdi:on"
    assert state.attributes["entity_picture"] == "/local/picture1.jpg"
