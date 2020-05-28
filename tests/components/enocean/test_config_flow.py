"""Tests for EnOcean config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.enocean.config_flow import EnOceanFlowHandler
from homeassistant.components.enocean.const import DOMAIN
from homeassistant.const import CONF_DEVICE

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry


async def test_user_flow_cannot_create_multiple_instances(hass):
    """Test that the user flow aborts if an instance is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/already/configured/path"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.enocean.dongle.validate_path", Mock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_with_detected_dongle(hass):
    """Test the user flow with a detected ENOcean dongle."""
    FAKE_DONGLE_PATH = "/fake/dongle"

    with patch(
        "homeassistant.components.enocean.dongle.detect",
        Mock(return_value=[FAKE_DONGLE_PATH]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "detect"
    devices = result["data_schema"].schema.get("device").container
    assert FAKE_DONGLE_PATH in devices
    assert EnOceanFlowHandler.MANUAL_PATH_VALUE in devices


async def test_user_flow_with_no_detected_dongle(hass):
    """Test the user flow with a detected ENOcean dongle."""
    with patch("homeassistant.components.enocean.dongle.detect", Mock(return_value=[])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_valid_path(hass):
    """Test the detection flow with a valid path selected."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        "homeassistant.components.enocean.dongle.validate_path", Mock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_detection_flow_with_custom_path(hass):
    """Test the detection flow with custom path selected."""
    USER_PROVIDED_PATH = EnOceanFlowHandler.MANUAL_PATH_VALUE

    with patch(
        "homeassistant.components.enocean.dongle.validate_path", Mock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "manual"


async def test_detection_flow_with_invalid_path(hass):
    """Test the detection flow with an invalid path selected."""
    USER_PROVIDED_PATH = "/invalid/path"

    with patch(
        "homeassistant.components.enocean.dongle.validate_path",
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "detect"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "detect"
    assert CONF_DEVICE in result["errors"]


async def test_manual_flow_with_valid_path(hass):
    """Test the manual flow with a valid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        "homeassistant.components.enocean.dongle.validate_path", Mock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}, data={CONF_DEVICE: USER_PROVIDED_PATH}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == USER_PROVIDED_PATH


async def test_manual_flow_with_invalid_path(hass):
    """Test the manual flow with an invalid path."""
    USER_PROVIDED_PATH = "/user/provided/path"

    with patch(
        "homeassistant.components.enocean.dongle.validate_path",
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

    with patch(
        "homeassistant.components.enocean.dongle.validate_path", Mock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=DATA_TO_IMPORT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == DATA_TO_IMPORT[CONF_DEVICE]


async def test_import_flow_with_invalid_path(hass):
    """Test the import flow with an invalid path."""
    DATA_TO_IMPORT = {CONF_DEVICE: "/invalid/path/to/import"}

    with patch(
        "homeassistant.components.enocean.dongle.validate_path",
        Mock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=DATA_TO_IMPORT
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_dongle_path"
