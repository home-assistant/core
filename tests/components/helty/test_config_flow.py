"""Test the Helty Flow config flow."""

from unittest.mock import AsyncMock

from pyhelty import HeltyConnectionError, HeltyError
import pytest

from homeassistant.components.helty.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_NAME, HOST, PORT

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT}


async def test_user_flow(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == DEVICE_NAME
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a connection error is shown, then the flow recovers."""
    mock_helty_client.async_get_name.side_effect = HeltyConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_helty_client.async_get_name.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_empty_name(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test an empty device name surfaces as an unknown error, then recovers."""
    mock_helty_client.async_get_name.return_value = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_helty_client.async_get_name.return_value = DEVICE_NAME
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if the same unit is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an entry with a new address."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {CONF_HOST: "192.168.20.99", CONF_PORT: PORT}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new_input


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (HeltyConnectionError, "cannot_connect"),
        (HeltyError, "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors are shown during reconfigure, then the flow recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_helty_client.async_get_name.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    new_input = {CONF_HOST: "192.168.20.99", CONF_PORT: PORT}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_helty_client.async_get_name.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new_input


async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring against a different unit is rejected."""
    mock_config_entry.add_to_hass(hass)
    mock_helty_client.async_get_name.return_value = "Another Helty"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.20.99", CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
