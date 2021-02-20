"""Test the buienradar2 config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.buienradar.const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_DIMENSION,
    CONF_SENSOR,
    CONF_WEATHER,
    DOMAIN,
)
from homeassistant.const import CONF_DOMAIN, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.common import MockConfigEntry

TEST_LATITUDE = 51.65
TEST_LONGITUDE = 5.7
TEST_NAME = "test"
TEST_FORECAST = True
TEST_DIMENSION = 512
TEST_DELTA = 600
TEST_COUNTRY = "NL"
TEST_TIMEFRAME = 60


async def test_config_flow_setup_camera(hass):
    """Test setup of camera."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DOMAIN: "Camera"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "camera"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_NAME, CONF_DIMENSION: 512, CONF_COUNTRY: "NL"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_DIMENSION: 512,
        CONF_COUNTRY: "NL",
        CONF_WEATHER: False,
        CONF_CAMERA: True,
        CONF_SENSOR: False,
    }


async def test_config_flow_setup_weather(hass):
    """Test setup of weather."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DOMAIN: "Weather"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "weather"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: TEST_NAME,
                CONF_LATITUDE: TEST_LATITUDE,
                CONF_LONGITUDE: TEST_LONGITUDE,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: True,
        CONF_CAMERA: False,
        CONF_SENSOR: True,
    }


async def test_config_flow_already_configured_camera(hass):
    """Test already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: TEST_NAME,
            CONF_DIMENSION: 512,
            CONF_COUNTRY: "NL",
            CONF_WEATHER: False,
            CONF_CAMERA: True,
            CONF_SENSOR: False,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DOMAIN: "Camera"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "camera"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: TEST_NAME, CONF_DIMENSION: 512, CONF_COUNTRY: "NL"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "camera"
    assert result["errors"] == {"base": "already_configured"}


async def test_config_flow_already_configured_weather(hass):
    """Test already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: False,
            CONF_SENSOR: True,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DOMAIN: "Weather"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "weather"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "weather"
    assert result["errors"] == {"base": "already_configured"}


async def test_import_camera(hass):
    """Test import of camera."""

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: TEST_NAME,
                CONF_DIMENSION: TEST_DIMENSION,
                CONF_COUNTRY: TEST_COUNTRY,
                CONF_CAMERA: True,
                CONF_SENSOR: False,
                CONF_WEATHER: False,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_DIMENSION: 512,
        CONF_COUNTRY: "NL",
        CONF_WEATHER: False,
        CONF_CAMERA: True,
        CONF_SENSOR: False,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_NAME: TEST_NAME,
            CONF_DIMENSION: TEST_DIMENSION,
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_CAMERA: True,
            CONF_SENSOR: False,
            CONF_WEATHER: False,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_weather(hass):
    """Test import of camera."""

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: TEST_NAME,
                CONF_LATITUDE: TEST_LATITUDE,
                CONF_LONGITUDE: TEST_LONGITUDE,
                CONF_CAMERA: False,
                CONF_SENSOR: True,
                CONF_WEATHER: True,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: True,
        CONF_CAMERA: False,
        CONF_SENSOR: True,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_CAMERA: False,
            CONF_SENSOR: True,
            CONF_WEATHER: True,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
