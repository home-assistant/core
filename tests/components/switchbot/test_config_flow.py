"""Test the switchbot config flow."""

from homeassistant.components.switchbot.config_flow import NotConnectedError
from homeassistant.components.switchbot.const import (
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    CONF_SCAN_TIMEOUT,
    CONF_TIME_BETWEEN_UPDATE_COMMAND,
)
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
    USER_INPUT_CURTAIN,
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

    # test curtain device creation.

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_CURTAIN,
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_MAC: "e7:89:43:90:90:90",
        CONF_NAME: "test-name",
        CONF_PASSWORD: "test-password",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1


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
    with _patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TIME_BETWEEN_UPDATE_COMMAND: 60,
                CONF_RETRY_COUNT: 3,
                CONF_RETRY_TIMEOUT: 5,
                CONF_SCAN_TIMEOUT: 5,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TIME_BETWEEN_UPDATE_COMMAND] == 60
    assert result["data"][CONF_RETRY_COUNT] == 3
    assert result["data"][CONF_RETRY_TIMEOUT] == 5
    assert result["data"][CONF_SCAN_TIMEOUT] == 5

    assert len(mock_setup_entry.mock_calls) == 1

    # Test changing of entry options.

    with _patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TIME_BETWEEN_UPDATE_COMMAND: 66,
                CONF_RETRY_COUNT: 6,
                CONF_RETRY_TIMEOUT: 6,
                CONF_SCAN_TIMEOUT: 6,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TIME_BETWEEN_UPDATE_COMMAND] == 66
    assert result["data"][CONF_RETRY_COUNT] == 6
    assert result["data"][CONF_RETRY_TIMEOUT] == 6
    assert result["data"][CONF_SCAN_TIMEOUT] == 6

    assert len(mock_setup_entry.mock_calls) == 1
