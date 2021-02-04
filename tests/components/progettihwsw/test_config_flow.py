"""Test the ProgettiHWSW Automation config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.progettihwsw.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

mock_value_step_user = {
    "title": "1R & 1IN Board",
    "relay_count": 1,
    "input_count": 1,
    "is_old": False,
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_value_step_rm = {
        "relay_1": "bistable",  # Mocking a single relay board instance.
    }

    with patch(
        "homeassistant.components.progettihwsw.config_flow.ProgettiHWSWAPI.check_board",
        return_value=mock_value_step_user,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "", CONF_PORT: 80},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "relay_modes"
    assert result2["errors"] == {}

    with patch(
        "homeassistant.components.progettihwsw.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.progettihwsw.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            mock_value_step_rm,
        )

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["data"]
    assert result3["data"]["title"] == "1R & 1IN Board"
    assert result3["data"]["is_old"] is False
    assert result3["data"]["relay_count"] == result3["data"]["input_count"] == 1


async def test_form_cannot_connect(hass):
    """Test we handle unexisting board."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.progettihwsw.config_flow.ProgettiHWSWAPI.check_board",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "", CONF_PORT: 80},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_existing_entry_exception(hass):
    """Test we handle existing board."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "", CONF_PORT: 80},
    )

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_form_user_exception(hass):
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.progettihwsw.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "", CONF_PORT: 80},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}
