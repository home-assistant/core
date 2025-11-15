"""Test the MTA config flow."""

from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.components.mta.const import (
    CONF_LINE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(
    hass: HomeAssistant, mock_nyct_feed_config_flow: MagicMock
) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"


async def test_form_stop_step(
    hass: HomeAssistant, mock_nyct_feed_config_flow: MagicMock
) -> None:
    """Test the stop step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    assert result["errors"] == {}


async def test_form_create_entry(
    hass: HomeAssistant, mock_nyct_feed_config_flow: MagicMock
) -> None:
    """Test we can complete the flow and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127N"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1 Line - Times Sq - 42 St (N direction)"
    assert result["data"] == {
        CONF_LINE: "1",
        CONF_STOP_ID: "127N",
        CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
    }


async def test_form_already_configured(
    hass: HomeAssistant, mock_nyct_feed_config_flow: MagicMock
) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LINE: "1",
            CONF_STOP_ID: "127N",
            CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
        },
        unique_id="1_127N",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127N"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_connection_error(
    hass: HomeAssistant, mock_nyct_feed_config_flow: MagicMock
) -> None:
    """Test we handle connection errors."""
    mock_instance = mock_nyct_feed_config_flow.return_value
    mock_instance.get_arrivals.side_effect = Exception("Connection error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127S"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
