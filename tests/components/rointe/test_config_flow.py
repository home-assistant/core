"""Test the Rointe config flow."""

import sys
from unittest.mock import patch

from rointesdk.rointe_api import ApiResponse

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.rointe.const import (
    CONF_INSTALLATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

from .common import LOCAL_ID, PASSWORD, USERNAME


async def test_user_flow(hass, setup_rointe_login_ok):
    """Test the user flow, both in case of success and with a duplicated entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.rointe.config_flow.RointeAPI.get_installations",
        ) as mock_get_installations,
        patch.object(
            sys.modules["homeassistant.components.rointe"],
            "async_setup_entry",
            return_value=True,
        ),
    ):
        # Prepare mocks.
        mock_get_installations.return_value = ApiResponse(
            True, {"install-0001": "My Home", "install-0002": "Summer Place"}, None
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "installation"
        assert result2["errors"] is None

        data_schema = result2.get("data_schema", None)
        assert data_schema and data_schema.schema

        in_schema = data_schema.schema[CONF_INSTALLATION]

        assert in_schema.container["install-0001"] == "My Home"
        assert in_schema.container["install-0002"] == "Summer Place"

        # Continue to final selection.
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_INSTALLATION: "install-0001"}
        )

        assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        # Restart the configuration to check if a duplicated installation throws an error.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] is None

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

        # Continue to final selection.
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_INSTALLATION: "install-0001"}
        )

        assert result3["type"] == data_entry_flow.FlowResultType.ABORT
        assert result3["reason"] == "already_configured"


async def test_invalid_installations(hass, setup_rointe_login_ok):
    """Test the user flow when an error retrieving the installations occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rointe.config_flow.RointeAPI.get_installations",
        return_value=ApiResponse(
            False, LOCAL_ID, "No response from API in get_installations()"
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "user"
        assert result2["errors"] == {"base": "unable_get_installations"}


async def test_user_flow_invalid_password(hass):
    """Test user flow with invalid password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rointe.config_flow.RointeAPI.initialize_authentication",
        return_value=ApiResponse(False, None, "invalid_auth"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}
