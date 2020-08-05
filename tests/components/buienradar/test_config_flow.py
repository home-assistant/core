"""Test the buienradar2 config flow."""
from homeassistant import config_entries
from homeassistant.components.buienradar.const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_SENSOR,
    CONF_WEATHER,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

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
            CONF_CAMERA: True,
            CONF_COUNTRY: "NL",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: True,
        CONF_CAMERA: True,
        CONF_SENSOR: True,
        CONF_COUNTRY: "NL",
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_setup_without_camera(hass):
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
            CONF_CAMERA: False,
            CONF_COUNTRY: "NL",
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
        CONF_COUNTRY: "NL",
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
            CONF_CAMERA: True,
            CONF_COUNTRY: "NL",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
        CONF_WEATHER: True,
        CONF_CAMERA: True,
        CONF_SENSOR: True,
        CONF_COUNTRY: "NL",
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
            CONF_CAMERA: True,
            CONF_COUNTRY: "NL",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_NAME: "name_exists"}

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()
