"""Test the ADS config flow."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call

import pyads
import pytest

from homeassistant.components.ads.const import CONF_LOCAL_NET_ID, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockPyadsLocalNetId
from .const import AMS_NET_ID, AUTO_NET_ID, LOCAL_NET_ID

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_DEVICE: AMS_NET_ID,
    CONF_IP_ADDRESS: "192.168.1.10",
    CONF_PORT: 851,
}


@pytest.mark.usefixtures("mock_setup_entry", "mock_pyads_connection")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AMS_NET_ID
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_pyads_connection")
async def test_user_flow_with_local_net_id(
    hass: HomeAssistant, mock_pyads_local_net_id: MockPyadsLocalNetId
) -> None:
    """Test the user flow configures a local AMS NetID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_LOCAL_NET_ID: LOCAL_NET_ID}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCAL_NET_ID] == LOCAL_NET_ID
    assert mock_pyads_local_net_id.open_port.call_count == 2
    assert mock_pyads_local_net_id.set_local_address.call_args_list == [
        call(LOCAL_NET_ID),
        call(AUTO_NET_ID),
    ]
    assert mock_pyads_local_net_id.close_port.call_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_local_net_id_restored_after_connect_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test a failed validation still restores the prior local AMS NetID."""
    mock_pyads_connection.return_value.read_state.side_effect = pyads.ADSError(
        text="timeout"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_LOCAL_NET_ID: LOCAL_NET_ID}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_pyads_local_net_id.set_local_address.call_args_list == [
        call(LOCAL_NET_ID),
        call(AUTO_NET_ID),
    ]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_invalid_local_net_id(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test the user flow rejects an invalid local AMS NetID."""
    mock_pyads_local_net_id.set_local_address.side_effect = ValueError(
        "invalid AMS NetID"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_LOCAL_NET_ID: LOCAL_NET_ID}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_net_id"}
    mock_pyads_local_net_id.close_port.assert_called_once()
    mock_pyads_connection.assert_not_called()


CONNECT_ERRORS = [
    pytest.param(
        lambda mock: setattr(
            mock.return_value.read_state, "side_effect", pyads.ADSError(text="timeout")
        ),
        "cannot_connect",
        id="ads_error",
    ),
    pytest.param(
        lambda mock: setattr(mock, "side_effect", ValueError("no valid netid")),
        "invalid_net_id",
        id="invalid_net_id",
    ),
    pytest.param(
        lambda mock: setattr(
            mock.return_value.open, "side_effect", RuntimeError("router down")
        ),
        "cannot_connect",
        id="router_down",
    ),
    pytest.param(
        lambda mock: setattr(mock.return_value.read_state, "side_effect", TypeError),
        "unknown",
        id="unknown",
    ),
]


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("configure_mock", "error"), CONNECT_ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    configure_mock: Callable[[MagicMock], None],
    error: str,
) -> None:
    """Test the user flow recovers from errors."""
    configure_mock(mock_pyads_connection)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pyads_connection.side_effect = None
    mock_pyads_connection.return_value.open.side_effect = None
    mock_pyads_connection.return_value.read_state.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_user_flow_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only a single entry can be configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry", "mock_pyads_connection")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing the YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AMS_NET_ID
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(("configure_mock", "reason"), CONNECT_ERRORS)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyads_connection: MagicMock,
    configure_mock: Callable[[MagicMock], None],
    reason: str,
) -> None:
    """Test the import flow aborts on errors."""
    configure_mock(mock_pyads_connection)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    mock_setup_entry.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry", "mock_pyads_connection")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the ADS connection."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    new_input = {**USER_INPUT, CONF_PORT: 852}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new_input


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test the reconfigure flow recovers from connection errors."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    mock_pyads_connection.return_value.read_state.side_effect = pyads.ADSError(
        text="timeout"
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_PORT: 852}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data == original_data


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_clears_optional_fields(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test clearing optional fields drops them instead of storing blanks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={**USER_INPUT, CONF_LOCAL_NET_ID: LOCAL_NET_ID},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_IP_ADDRESS: "", CONF_LOCAL_NET_ID: ""},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_DEVICE: AMS_NET_ID, CONF_PORT: 851}
    # An empty address would be passed through instead of derived from the NetID.
    assert mock_pyads_connection.call_args == call(AMS_NET_ID, 851, None)


@pytest.mark.usefixtures("mock_setup_entry", "mock_pyads_connection")
async def test_reconfigure_flow_updates_title(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring to another PLC retitles the entry."""
    mock_config_entry.add_to_hass(hass)
    new_net_id = "192.168.1.20.1.1"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_DEVICE: new_net_id}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.title == new_net_id
