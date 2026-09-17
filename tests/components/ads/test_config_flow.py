"""Test the ADS config flow."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import AMS_NET_ID

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
        lambda mock: setattr(mock.return_value.read_state, "side_effect", RuntimeError),
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
