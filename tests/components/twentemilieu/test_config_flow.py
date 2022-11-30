"""Tests for the Twente Milieu config flow."""
from unittest.mock import MagicMock

from twentemilieu import TwenteMilieuAddressError, TwenteMilieuConnectionError

from homeassistant import config_entries
from homeassistant.components.twentemilieu import config_flow
from homeassistant.components.twentemilieu.const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_twentemilieu_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "12345"
    assert result2.get("data") == {
        CONF_ID: 12345,
        CONF_POST_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_HOUSE_LETTER: "A",
    }


async def test_invalid_address(
    hass: HomeAssistant,
    mock_twentemilieu_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test full user flow when the user enters an incorrect address.

    This tests also tests if the user recovers from it by entering a valid
    address in the second attempt.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    mock_twentemilieu_config_flow.unique_id.side_effect = TwenteMilieuAddressError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"base": "invalid_address"}
    assert "flow_id" in result2

    mock_twentemilieu_config_flow.unique_id.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "12345"
    assert result3.get("data") == {
        CONF_ID: 12345,
        CONF_POST_CODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_HOUSE_LETTER: None,
    }


async def test_connection_error(
    hass: HomeAssistant,
    mock_twentemilieu_config_flow: MagicMock,
) -> None:
    """Test we show user form on Twente Milieu connection error."""
    mock_twentemilieu_config_flow.unique_id.side_effect = TwenteMilieuConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_address_already_set_up(
    hass: HomeAssistant,
    mock_twentemilieu_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if address has already been set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
