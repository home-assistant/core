"""Tests for the Twente Milieu config flow."""

from unittest.mock import MagicMock

import pytest
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

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "12345"
    assert config_entry.data == {
        CONF_HOUSE_LETTER: "A",
        CONF_HOUSE_NUMBER: "1",
        CONF_ID: 12345,
        CONF_POST_CODE: "1234AB",
    }
    assert not config_entry.options


async def test_invalid_address(
    hass: HomeAssistant,
    mock_twentemilieu: MagicMock,
) -> None:
    """Test full user flow when the user enters an incorrect address.

    This tests also tests if the user recovers from it by entering a valid
    address in the second attempt.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_twentemilieu.unique_id.side_effect = TwenteMilieuAddressError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_address"}

    mock_twentemilieu.unique_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "12345"
    assert config_entry.data == {
        CONF_HOUSE_LETTER: None,
        CONF_HOUSE_NUMBER: "1",
        CONF_ID: 12345,
        CONF_POST_CODE: "1234AB",
    }
    assert not config_entry.options


async def test_connection_error(
    hass: HomeAssistant,
    mock_twentemilieu: MagicMock,
) -> None:
    """Test we show user form on Twente Milieu connection error."""
    mock_twentemilieu.unique_id.side_effect = TwenteMilieuConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_twentemilieu.unique_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "12345"
    assert config_entry.data == {
        CONF_HOUSE_LETTER: "A",
        CONF_HOUSE_NUMBER: "1",
        CONF_ID: 12345,
        CONF_POST_CODE: "1234AB",
    }
    assert not config_entry.options


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_address_already_set_up(
    hass: HomeAssistant,
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
