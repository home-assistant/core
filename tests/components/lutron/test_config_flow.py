"""Test the lutron config flow."""

from email.message import Message
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError

import pytest

from homeassistant.components.lutron.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_DATA_STEP = {
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: "lutron",
    CONF_PASSWORD: "integration",
}


async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("homeassistant.components.lutron.config_flow.Lutron.load_xml_db"),
        patch("homeassistant.components.lutron.config_flow.Lutron.guid", "12345678901"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "Lutron"

        assert result["data"] == MOCK_DATA_STEP


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (HTTPError("", 404, "", Message(), None), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lutron.config_flow.Lutron.load_xml_db",
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    with (
        patch("homeassistant.components.lutron.config_flow.Lutron.load_xml_db"),
        patch("homeassistant.components.lutron.config_flow.Lutron.guid", "12345678901"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "Lutron"

        assert result["data"] == MOCK_DATA_STEP


async def test_flow_incorrect_guid(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test configuring flow with incorrect guid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("homeassistant.components.lutron.config_flow.Lutron.load_xml_db"),
        patch("homeassistant.components.lutron.config_flow.Lutron.guid", "12345"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch("homeassistant.components.lutron.config_flow.Lutron.load_xml_db"),
        patch("homeassistant.components.lutron.config_flow.Lutron.guid", "12345678901"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA_STEP, unique_id="12345678901")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


MOCK_DATA_IMPORT = {
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: "lutron",
    CONF_PASSWORD: "integration",
}
