"""Test the Airthings config flow."""
from unittest.mock import patch

import airthings

from spencerassistant import config_entries
from spencerassistant.components.airthings.const import CONF_ID, CONF_SECRET, DOMAIN
from spencerassistant.core import spencerAssistant
from spencerassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_ID: "client_id",
    CONF_SECRET: "secret",
}


async def test_form(hass: spencerAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("airthings.get_token", return_value="test_token",), patch(
        "spencerassistant.components.airthings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Airthings"
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: spencerAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=airthings.AirthingsAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: spencerAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=airthings.AirthingsConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: spencerAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "airthings.get_token",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_flow_entry_already_exists(hass: spencerAssistant) -> None:
    """Test user input for config_entry that already exists."""

    first_entry = MockConfigEntry(
        domain="airthings",
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_ID],
    )
    first_entry.add_to_hass(hass)

    with patch("airthings.get_token", return_value="token"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
