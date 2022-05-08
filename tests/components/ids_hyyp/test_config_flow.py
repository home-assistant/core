"""Test the ids_hyyp config flow."""

from pyhyypapi import HTTPError, HyypApiError, InvalidURL

from homeassistant.components.ids_hyyp.const import (
    ATTR_ARM_CODE,
    ATTR_BYPASS_CODE,
    CONF_PKG,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TIMEOUT, CONF_TOKEN
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import USER_INPUT, init_integration, patch_async_setup_entry

DOMAIN = "ids_hyyp"


async def test_user_form_valid_input(hass, ids_hyyp_config_flow):
    """Test the user initiated form with valid input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == {
        CONF_TOKEN: "12341",
        CONF_PKG: "com.hyyp247.home",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_exception(hass, ids_hyyp_config_flow):
    """Test we handle exception on user form."""

    ids_hyyp_config_flow.side_effect = InvalidURL

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    ids_hyyp_config_flow.side_effect = HTTPError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    ids_hyyp_config_flow.side_effect = HyypApiError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    ids_hyyp_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_options_flow(hass):
    """Test updating options."""
    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TIMEOUT: 30,
                ATTR_ARM_CODE: "1111",
                ATTR_BYPASS_CODE: "2222",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TIMEOUT] == 30
    assert result["data"][ATTR_ARM_CODE] == "1111"
    assert result["data"][ATTR_BYPASS_CODE] == "2222"

    assert len(mock_setup_entry.mock_calls) == 1

    # Test changing of entry options.

    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TIMEOUT: 33,
                ATTR_ARM_CODE: "1111",
                ATTR_BYPASS_CODE: "2222",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_TIMEOUT] == 33
    assert result["data"][ATTR_ARM_CODE] == "1111"
    assert result["data"][ATTR_BYPASS_CODE] == "2222"

    assert len(mock_setup_entry.mock_calls) == 1
