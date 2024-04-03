"""Test the swiss_public_transport config flow."""

from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_DATA_STEP = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}


async def test_flow_user_init_data_success(hass: HomeAssistant) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_DATA_STEP


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect"),
        (OpendataTransportError(), "bad_config"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_error_and_recover(
    hass: HomeAssistant, raise_error, text_error
) -> None:
    """Test unknown errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_STEP,
        unique_id=f"{MOCK_DATA_STEP[CONF_START]} {MOCK_DATA_STEP[CONF_DESTINATION]}",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


MOCK_DATA_IMPORT = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
    CONF_NAME: "test_name",
}


async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA_IMPORT,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_DATA_IMPORT
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect"),
        (OpendataTransportError(), "bad_config"),
        (IndexError(), "unknown"),
    ],
)
async def test_import_error(hass: HomeAssistant, raise_error, text_error) -> None:
    """Test import flow cannot_connect error."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA_IMPORT,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == text_error


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test we abort import when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_IMPORT,
        unique_id=f"{MOCK_DATA_IMPORT[CONF_START]} {MOCK_DATA_IMPORT[CONF_DESTINATION]}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA_IMPORT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
