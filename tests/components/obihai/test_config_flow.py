"""Test the Obihai config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.obihai.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DHCP_SERVICE_INFO, USER_INPUT, MockPyObihai, get_schema_suggestion

VALIDATE_AUTH_PATCH = "homeassistant.components.obihai.config_flow.validate_auth"

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(VALIDATE_AUTH_PATCH, return_value=MockPyObihai()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.10.30"
    assert result["data"] == {**USER_INPUT}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_auth_failure(hass: HomeAssistant) -> None:
    """Test we get the authentication error for user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(VALIDATE_AUTH_PATCH, return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


async def test_connect_failure(hass: HomeAssistant, mock_gaierror: Generator) -> None:
    """Test we get the connection error for user flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_dhcp_flow(hass: HomeAssistant) -> None:
    """Test that DHCP discovery works."""

    with patch(
        VALIDATE_AUTH_PATCH,
        return_value=MockPyObihai(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DHCP_SERVICE_INFO,
            context={"source": config_entries.SOURCE_DHCP},
        )

        flows = hass.config_entries.flow.async_progress()
        assert result["type"] is FlowResultType.FORM
        assert len(flows) == 1
        assert (
            get_schema_suggestion(result["data_schema"].schema, CONF_USERNAME)
            == USER_INPUT[CONF_USERNAME]
        )
        assert (
            get_schema_suggestion(result["data_schema"].schema, CONF_PASSWORD)
            == USER_INPUT[CONF_PASSWORD]
        )
        assert (
            get_schema_suggestion(result["data_schema"].schema, CONF_HOST)
            == DHCP_SERVICE_INFO.ip
        )
        assert flows[0].get("context", {}).get("source") == config_entries.SOURCE_DHCP

        # Verify we get dropped into the normal user flow with non-default credentials
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_dhcp_flow_auth_failure(hass: HomeAssistant) -> None:
    """Test that DHCP fails if creds aren't default."""

    with patch(
        VALIDATE_AUTH_PATCH,
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DHCP_SERVICE_INFO,
            context={"source": config_entries.SOURCE_DHCP},
        )

        assert result["step_id"] == "dhcp_confirm"
        assert get_schema_suggestion(result["data_schema"].schema, CONF_USERNAME) == ""
        assert get_schema_suggestion(result["data_schema"].schema, CONF_PASSWORD) == ""
        assert (
            get_schema_suggestion(result["data_schema"].schema, CONF_HOST)
            == DHCP_SERVICE_INFO.ip
        )

    # Verify we get dropped into the normal user flow with non-default credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: DHCP_SERVICE_INFO.ip,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )

    assert result["errors"]["base"] == "invalid_auth"
    assert result["step_id"] == "user"
