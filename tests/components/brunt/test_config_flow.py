"""Test the Brunt config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.brunt.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

CONF = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}


async def _flow_submit(hass, context={"source": config_entries.SOURCE_USER}, data=CONF):
    """Submit a flow to hass."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context=context,
        data=data,
    )


async def test_form(hass):
    """Test we get the form."""
    result = await _flow_submit(hass, data=None)
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.brunt.config_flow.validate_input", return_value=None
    ), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test we get the form."""

    with patch(
        "homeassistant.components.brunt.config_flow.validate_input", return_value=None
    ), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await _flow_submit(hass, {"source": config_entries.SOURCE_IMPORT})
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_duplicate_login(hass):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.brunt.config_flow.validate_input", return_value=None
    ), patch(
        "homeassistant.components.brunt.async_setup_entry",
        return_value=True,
    ):
        result = await _flow_submit(hass, {"source": config_entries.SOURCE_IMPORT})
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured_account"


async def test_form_duplicate_login(hass):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.brunt.config_flow.validate_input", return_value=None
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize("side_effect", ["cannot_connect", "invalid_auth", "unknown"])
async def test_form_error(hass, side_effect):
    """Test we handle cannot connect."""
    with patch(
        "homeassistant.components.brunt.config_flow.validate_input",
        return_value={"base": side_effect},
    ):
        result = await _flow_submit(hass)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": side_effect}


@pytest.mark.parametrize("user_in", [CONF, None])
async def test_reauth(hass, user_in):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="test-username",
        unique_id="test-username",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.brunt.config_flow.validate_input",
        return_value={"errors": "invalid_auth"},
    ):
        result = await _flow_submit(
            hass,
            {
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": entry.unique_id,
                "entry_id": entry.entry_id,
            },
            user_in,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
    with patch(
        "homeassistant.components.brunt.config_flow.validate_input",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data["username"] == "test-username"
        assert entry.data["password"] == "test"
