"""Define tests for the triggercmd config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.triggercmd.const import CONF_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

invalid_token_with_length_100_or_more = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjEyMzQ1Njc4OTBxd2VydHl1aW9wYXNkZiIsImlhdCI6MTcxOTg4MTU4M30.E4T2S4RQfuI2ww74sUkkT-wyTGrV5_VDkgUdae5yo4E"
invalid_token_id = "1234567890qwertyuiopasdf"


@pytest.fixture
def mock_hub():
    """Create a mock hub."""
    with patch("homeassistant.components.triggercmd.hub.Hub") as mock_hub_class:
        mock_hub_instance = mock_hub_class.return_value
        mock_hub_instance.test_connection = MagicMock(return_value=True)
        yield mock_hub_instance


async def test_config_flow_initial_form(
    hass: HomeAssistant,
) -> None:
    """Test the initial step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM


async def test_config_flow_user_invalid_token(
    hass: HomeAssistant,
) -> None:
    """Test a valid jwt but invalid TRIGGERcmd token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.triggercmd.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}
    assert result["type"] == FlowResultType.FORM


async def test_config_flow_user_short_nontoken(
    hass: HomeAssistant,
) -> None:
    """Test the initial step of the config flow."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.triggercmd.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {CONF_TOKEN: "not-a-token"},
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_TOKEN: "invalid_token"}
    assert result["type"] == FlowResultType.FORM


async def test_config_flow_entry_already_configured(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    test_data = {
        CONF_TOKEN: invalid_token_with_length_100_or_more,
    }
    MockConfigEntry(
        domain=DOMAIN,
        data=test_data,
        unique_id=invalid_token_id,
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.triggercmd.config_flow.test_token",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.config_flow.test_connection",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_connection_error(hass: HomeAssistant) -> None:
    """Test a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with (
        patch(
            "homeassistant.components.triggercmd.config_flow.test_token",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.config_flow.test_connection",
            return_value={"connection": "connection_error"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "connection": "connection_error",
    }


async def test_config_flow_happy_path(
    hass: HomeAssistant,
) -> None:
    """Test config flow happy path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.triggercmd.config_flow.test_token",
            return_value=200,
        ),
        patch(
            "homeassistant.components.triggercmd.config_flow.test_connection",
            return_value={},
        ),
        patch(
            "homeassistant.components.triggercmd.config_flow.validate_input",
            return_value="my-hub-id",
        ),
        patch(
            "homeassistant.components.triggercmd.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: invalid_token_with_length_100_or_more},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
