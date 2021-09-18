"""Test the switchbot config flow."""

from unittest.mock import patch

from homeassistant.components.switchbot.config_flow import NotConnectedError
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.setup import async_setup_component

from . import (
    USER_INPUT,
    USER_INPUT_INVALID,
    USER_INPUT_UNSUPPORTED_DEVICE,
    YAML_CONFIG,
    _patch_async_setup_entry,
    init_integration,
)

DOMAIN = "switchbot"


async def test_user_form_valid_mac(hass):
    """Test the user initiated form with password and valid mac."""
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_MAC: "e7:89:43:99:99:99",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1

    # test duplicate device creation fails.

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_device"


async def test_user_form_unsupported_device(hass):
    """Test the user initiated form for unsupported device type."""
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_UNSUPPORTED_DEVICE,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "switchbot_unsupported_type"


async def test_user_form_invalid_device(hass):
    """Test the user initiated form for invalid device type."""
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_INVALID,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_async_step_import(hass):
    """Test the config import flow."""
    await async_setup_component(hass, "persistent_notification", {})

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=YAML_CONFIG
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_MAC: "e7:89:43:99:99:99",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_exception(hass, switchbot_config_flow):
    """Test we handle exception on user form."""
    await async_setup_component(hass, "persistent_notification", {})

    switchbot_config_flow.side_effect = NotConnectedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    switchbot_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_options_flow(hass):
    """Test updating options."""
    with patch("homeassistant.components.switchbot.PLATFORMS", []):
        entry = await init_integration(hass)

    assert entry.options["update_time"] == 60
    assert entry.options["retry_count"] == 3
    assert entry.options["retry_timeout"] == 5
    assert entry.options["scan_timeout"] == 5

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "update_time": 60,
                "retry_count": 3,
                "retry_timeout": 5,
                "scan_timeout": 5,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["update_time"] == 60
    assert result["data"]["retry_count"] == 3
    assert result["data"]["retry_timeout"] == 5
    assert result["data"]["scan_timeout"] == 5

    assert len(mock_setup_entry.mock_calls) == 0
