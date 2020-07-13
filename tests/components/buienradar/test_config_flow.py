"""Test the buienradar2 config flow."""
from homeassistant import config_entries
from homeassistant.components.buienradar.const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_DELTA,
    CONF_DIMENSION,
    CONF_FORECAST,
    CONF_SENSOR,
    CONF_TIMEFRAME,
    CONF_WEATHER,
    DOMAIN,
)
from homeassistant.const import CONF_INCLUDE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

TEST_LATITUDE = 51.65
TEST_LONGITUDE = 5.7
TEST_NAME = "test"
TEST_FORECAST = True
TEST_DIMENSION = 512
TEST_DELTA = 600
TEST_COUNTRY = "NL"
TEST_TIMEFRAME = 60


async def test_config_flow_setup_all(hass):
    """
    Test flow manually initialized by user.

    Setup all platforms.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: True,
            CONF_SENSOR: True,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_weather"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FORECAST: TEST_FORECAST}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_camera"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DELTA: TEST_DELTA,
            CONF_DIMENSION: TEST_DIMENSION,
            CONF_COUNTRY: TEST_COUNTRY,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_sensor"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TIMEFRAME: TEST_TIMEFRAME}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: True, CONF_FORECAST: TEST_FORECAST},
        CONF_CAMERA: {
            CONF_INCLUDE: True,
            CONF_DIMENSION: TEST_DIMENSION,
            CONF_DELTA: TEST_DELTA,
            CONF_COUNTRY: TEST_COUNTRY,
        },
        CONF_SENSOR: {CONF_INCLUDE: True, CONF_TIMEFRAME: TEST_TIMEFRAME},
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_setup_weather(hass):
    """
    Test flow manually initialized by user.

    Setup weather platform
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: False,
            CONF_SENSOR: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_weather"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FORECAST: TEST_FORECAST}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: True, CONF_FORECAST: TEST_FORECAST},
        CONF_CAMERA: {CONF_INCLUDE: False},
        CONF_SENSOR: {CONF_INCLUDE: False},
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_setup_camera(hass):
    """
    Test flow manually initialized by user.

    Setup camera platform
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: False,
            CONF_CAMERA: True,
            CONF_SENSOR: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_camera"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DELTA: TEST_DELTA,
            CONF_DIMENSION: TEST_DIMENSION,
            CONF_COUNTRY: TEST_COUNTRY,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: False},
        CONF_CAMERA: {
            CONF_INCLUDE: True,
            CONF_DIMENSION: TEST_DIMENSION,
            CONF_DELTA: TEST_DELTA,
            CONF_COUNTRY: TEST_COUNTRY,
        },
        CONF_SENSOR: {CONF_INCLUDE: False},
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_setup_sensor(hass):
    """
    Test flow manually initialized by user.

    Setup sensor platform.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: False,
            CONF_CAMERA: False,
            CONF_SENSOR: True,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_sensor"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TIMEFRAME: TEST_TIMEFRAME}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: False},
        CONF_CAMERA: {CONF_INCLUDE: False},
        CONF_SENSOR: {CONF_INCLUDE: True, CONF_TIMEFRAME: TEST_TIMEFRAME},
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_setup_weather_sensor(hass):
    """
    Test flow manually initialized by user.

    Setup weather and sensor platforms
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: False,
            CONF_SENSOR: True,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_weather"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FORECAST: TEST_FORECAST}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_sensor"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TIMEFRAME: TEST_TIMEFRAME}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: True, CONF_FORECAST: TEST_FORECAST},
        CONF_CAMERA: {CONF_INCLUDE: False},
        CONF_SENSOR: {CONF_INCLUDE: True, CONF_TIMEFRAME: TEST_TIMEFRAME},
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_already_configured(hass):
    """
    Test flow manually initialized by user.

    Setup all platforms.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: False,
            CONF_SENSOR: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_weather"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FORECAST: TEST_FORECAST}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: {CONF_INCLUDE: True, CONF_FORECAST: TEST_FORECAST},
        CONF_CAMERA: {CONF_INCLUDE: False},
        CONF_SENSOR: {CONF_INCLUDE: False},
    }

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: True,
            CONF_CAMERA: False,
            CONF_SENSOR: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_NAME: "name_exists"}

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_empty_selection(hass):
    """
    Test flow manually initialized by user.

    Setup all platforms.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: TEST_NAME,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_WEATHER: False,
            CONF_CAMERA: False,
            CONF_SENSOR: False,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "empty_selection"}
