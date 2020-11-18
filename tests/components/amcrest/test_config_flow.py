"""Test Amcrest config flow."""
from amcrest import AmcrestError, LoginError
from homeassistant import data_entry_flow
import pytest
from homeassistant.components.amcrest.amcrest_checker import AmcrestChecker

# from homeassistant import data_entry_flow
# from homeassistant.components.amcrest import config_flow
from homeassistant.components.amcrest.const import (
    AUTHENTICATION_LIST,
    CONF_BINARY_SENSOR_AUDIO_DETECTED,
    CONF_BINARY_SENSOR_AUDIO_DETECTED_POLLED,
    CONF_BINARY_SENSOR_MOTION_DETECTED,
    CONF_BINARY_SENSOR_MOTION_DETECTED_POLLED,
    CONF_BINARY_SENSOR_ONLINE,
    CONF_CONTROL_LIGHT,
    CONF_EVENTS,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_SENSOR_PTZ_PRESET,
    CONF_SENSOR_SDCARD,
    CONF_STREAM_SOURCE,
    DEFAULT_AUTHENTICATION,
    DEFAULT_CONTROL_LIGHT,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STREAM_SOURCE,
    DEVICES,
    DOMAIN,
    RESOLUTION_LIST,
    STREAM_SOURCE_LIST,
)
from homeassistant.const import (
    CONF_HOST,
    # CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
)

# from .test_device import MAC, MODEL, NAME, setup_axis_integration, vapix_session_request

# from tests.async_mock import patch
from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry

# from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_MAC = "ab:cd:ef:gh"
TEST_HOST2 = "5.6.7.8"
TEST_NAME = "Amcrest Camera"
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"
TEST_PORT = 80
TEST_MODEL = "model5"
TEST_SERIALNUMBER = "123456789"
TEST_UNIQUE_ID = f"{TEST_NAME}-{TEST_SERIALNUMBER}"


async def test_flow_manual_configuration(hass):
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
        new=AmcrestChecker,
    ) as mock_my_class:
        mock_my_class.serial_number = TEST_SERIALNUMBER
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: TEST_NAME,
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PORT: TEST_PORT,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == f"{DEFAULT_NAME}"
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
    }


async def test_flow_fails_already_configured(hass):
    """Test that config flow fails on already configured device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIALNUMBER,
        data={
            CONF_NAME: TEST_NAME,
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.amcrest.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
        new=AmcrestChecker,
    ) as mock_my_class:
        mock_my_class.serial_number = TEST_SERIALNUMBER
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: TEST_NAME,
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PORT: TEST_PORT,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_fails_faulty_credentials(hass):
    """Test that config flow fails on faulty credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
        side_effect=LoginError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: TEST_NAME,
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PORT: TEST_PORT,
            },
        )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_fails_device_unavailable(hass):
    """Test that config flow fails on device unavailable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
        side_effect=AmcrestError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: TEST_NAME,
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PORT: TEST_PORT,
            },
        )

    assert result["errors"] == {"base": "device_unavailable"}


async def test_option_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIALNUMBER,
        data={
            CONF_NAME: TEST_NAME,
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "configure_stream"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_STREAM_SOURCE: DEFAULT_STREAM_SOURCE,
            CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
            CONF_RESOLUTION: DEFAULT_RESOLUTION,
            CONF_AUTHENTICATION: DEFAULT_AUTHENTICATION,
            CONF_CONTROL_LIGHT: DEFAULT_CONTROL_LIGHT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_BINARY_SENSORS: [],
            CONF_SENSORS: [],
            CONF_EVENTS: "",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_STREAM_SOURCE: DEFAULT_STREAM_SOURCE,
        CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
        CONF_RESOLUTION: DEFAULT_RESOLUTION,
        CONF_AUTHENTICATION: DEFAULT_AUTHENTICATION,
        CONF_CONTROL_LIGHT: DEFAULT_CONTROL_LIGHT,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_BINARY_SENSORS: [],
        CONF_SENSORS: [],
        CONF_EVENTS: "",
    }
