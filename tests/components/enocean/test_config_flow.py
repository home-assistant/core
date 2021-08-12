"""Tests for EnOcean config flow."""
from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import DOMAIN
from homeassistant.const import CONF_DEVICE

from tests.common import MockConfigEntry

DONGLE_VALIDATE_PATH_METHOD = "homeassistant.components.enocean.dongle.validate_path"
DONGLE_DETECT_METHOD = "homeassistant.components.enocean.dongle.detect"


async def test_user_flow_cannot_create_multiple_instances(hass):
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_dongle(hass):
    """Test the user flow with a detected ENOcean dongle."""
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get("device").container
    assert FAKE_DONGLE_PATH in devices
    assert EnOceanFlowHandler.MANUAL_PATH_VALUE in devices


async def test_user_flow_with_no_detected_dongle(hass):
    """Test the user flow with a detected ENOcean dongle."""
    with patch(DONGLE_DETECT_METHOD, Mock(return_value=[])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_valid_path(hass):
    """Test the detection flow with a valid path selected."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_detection_flow_with_custom_path(hass):
    """Test the detection flow with custom path selected."""
    USER_PROVIDED_PATH = EnOceanFlowHandler.MANUAL_PATH_VALUE
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)), patch(
        DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_invalid_path(hass):
    """Test the detection flow with an invalid path selected."""
    USER_PROVIDED_PATH = "/invalid/path"
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=False)), patch(
        DONGLE_DETECT_METHOD, Mock(return_value=[FAKE_DONGLE_PATH])
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "detect"},
            data={CONF_DEVICE: USER_PROVIDED_PATH},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "detect"
    assert CONF_DEVICE in result["errors"]


async def test_manual_flow_with_valid_path(hass):
    """Test the manual flow with a valid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_manual_flow_with_invalid_path(hass):
    """Test the manual flow with an invalid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        DONGLE_VALIDATE_PATH_METHOD,
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"
    assert CONF_DEVICE in result["errors"]


async def test_import_flow_with_valid_path(hass):
    """Test the import flow with a valid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/valid/path/to/import"}

    with patch(DONGLE_VALIDATE_PATH_METHOD, Mock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass):
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(
        DONGLE_VALIDATE_PATH_METHOD,
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=DATA_TO_IMPORT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_dongle_path"
