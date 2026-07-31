"""Test the Gatus Config flow."""

from unittest.mock import AsyncMock

from gatus_api import GatusClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_gatus_client")
async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form, validate the client, and create a successful entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example.com:8080"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gatus"
    assert result["data"] == {
        CONF_URL: "http://gatus.example.com:8080",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_gatus_client")
async def test_form_success_with_path(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form, validate the client, and create a successful entry with a sub-path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example.com:8080/gatus-instance/"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gatus"
    assert result["data"] == {
        CONF_URL: "http://gatus.example.com:8080/gatus-instance",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (GatusClientError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_form_failures_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_gatus_client: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test handling validation failures and ensuring the flow can completely recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_gatus_client.get_endpoints_statuses.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example.com:8080"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_gatus_client.get_endpoints_statuses.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example.com:8080"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that duplicate configurations for the same base URL abort early."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example.com:8080"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_gatus_client")
async def test_flow_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example2.com:8080/"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: "http://gatus.example2.com:8080",
    }


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (GatusClientError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_flow_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gatus_client: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test reconfigure flow errors and recover."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_gatus_client.get_endpoints_statuses.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example2.com:8080"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_gatus_client.get_endpoints_statuses.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example2.com:8080"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: "http://gatus.example2.com:8080",
    }


@pytest.mark.usefixtures("mock_gatus_client")
async def test_flow_reconfigure_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts if the new URL is already configured."""
    mock_config_entry.add_to_hass(hass)

    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.example3.com:8080"},
        entry_id="other_id",
    )
    other_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://gatus.example3.com:8080"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
