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


async def test_flow_user_init_data_success(hass: HomeAssistant) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.return_value = True
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "create_entry"
        assert result["result"].title == "test_start test_destination"

        assert {
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        } == result["data"]


async def test_flow_user_init_data_cannot_connect_error(hass: HomeAssistant) -> None:
    """Test cannot_connect errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = (
            OpendataTransportConnectionError()
        )
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_init_data_bad_config_error(hass: HomeAssistant) -> None:
    """Test bad_config errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = (
            OpendataTransportError()
        )
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "bad_config"


async def test_flow_user_init_data_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = IndexError()
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "unknown"


async def test_flow_user_init_data_unknown_error_and_recover(
    hass: HomeAssistant,
) -> None:
    """Test unknown errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = IndexError()
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "unknown"

        # Recover
        mock_OpendataTransport_instance.async_get_data.side_effect = None
        mock_OpendataTransport_instance.async_get_data.return_value = True
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            _result["flow_id"],
            user_input={
                CONF_START: "test_start",
                CONF_DESTINATION: "test_destination",
            },
        )

        assert result["type"] == "create_entry"
        assert result["result"].title == "test_start test_destination"

        assert {
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        } == result["data"]


MOCK_DATA = {
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
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.return_value = True
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_DATA
        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect_error(
    hass: HomeAssistant,
) -> None:
    """Test import flow cannot_connect error."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = (
            OpendataTransportConnectionError()
        )
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_import_bad_config_error(
    hass: HomeAssistant,
) -> None:
    """Test import flow bad_config error."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = (
            OpendataTransportError()
        )
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "bad_config"


async def test_import_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test import flow unknown error."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
        autospec=True,
    ) as mock_OpendataTransport:
        mock_OpendataTransport_instance = mock_OpendataTransport.return_value
        mock_OpendataTransport_instance.async_get_data.side_effect = IndexError()
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test we abort import when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
