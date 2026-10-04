"""Test the Axle configuration flow."""

from unittest.mock import AsyncMock

from aioaxlevpp import AxleAuthenticationError, AxleConnectionError, AxleError
import pytest

from homeassistant.components.axle_energy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user(hass: HomeAssistant) -> None:
    """Configure the feed through the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "test-token"}
    assert result["title"] == "Axle Energy"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (AxleAuthenticationError(), "invalid_auth"),
        (AxleConnectionError(), "cannot_connect"),
        (AxleError(), "cannot_retrieve"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant, mock_client: AsyncMock, error: Exception, message: str
) -> None:
    """Show recoverable setup failures."""
    mock_client.get_event.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}
    mock_client.get_event.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "replacement-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "replacement-token"}
    assert result["title"] == "Axle Energy"


async def test_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Reject the same key without making another API request."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.get_event.assert_not_called()


@pytest.mark.parametrize("api_key", ["replacement-token", "test-token"])
async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    api_key: str,
) -> None:
    """Reauthenticate the existing feed, including with an unchanged key."""
    mock_client.get_event.return_value = None
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert next(iter(result["data_schema"].schema)).description is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)
    mock_client.get_event.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (AxleAuthenticationError(), "invalid_auth"),
        (AxleConnectionError(), "cannot_connect"),
        (AxleError(), "cannot_retrieve"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    error: Exception,
    message: str,
) -> None:
    """Keep the existing key after a failed replacement and allow a retry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await mock_config_entry.start_reauth_flow(hass)
    mock_client.get_event.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "replacement-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert next(iter(result["data_schema"].schema)).description is None
    assert result["errors"] == {"base": message}
    assert mock_config_entry.data == {CONF_API_KEY: "test-token"}
    mock_setup_entry.assert_not_called()

    mock_client.get_event.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "replacement-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: "replacement-token"}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)


@pytest.mark.parametrize("api_key", ["replacement-token", "test-token"])
async def test_reauth_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    api_key: str,
) -> None:
    """Keep the flow open after a duplicate key and allow a retry."""
    assert await async_setup_component(hass, DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "other-token"})
    other_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert next(iter(result["data_schema"].schema)).description is None
    assert result["errors"] == {CONF_API_KEY: "already_configured"}
    assert mock_config_entry.data == {CONF_API_KEY: "test-token"}
    assert other_entry.data == {CONF_API_KEY: "other-token"}
    mock_client.get_event.assert_not_called()
    mock_setup_entry.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert other_entry.data == {CONF_API_KEY: "other-token"}
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry, other_entry]
    mock_client.get_event.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)


@pytest.mark.parametrize("api_key", ["replacement-token", "test-token"])
async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    api_key: str,
) -> None:
    """Reconfigure the existing feed, including with an unchanged key."""
    mock_client.get_event.return_value = None
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert next(iter(result["data_schema"].schema)).description == {
        "suggested_value": "test-token"
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)
    mock_client.get_event.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (AxleAuthenticationError(), "invalid_auth"),
        (AxleConnectionError(), "cannot_connect"),
        (AxleError(), "cannot_retrieve"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    error: Exception,
    message: str,
) -> None:
    """Keep the existing key after a failed replacement and allow a retry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await mock_config_entry.start_reconfigure_flow(hass)
    mock_client.get_event.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "replacement-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert next(iter(result["data_schema"].schema)).description == {
        "suggested_value": "test-token"
    }
    assert result["errors"] == {"base": message}
    assert mock_config_entry.data == {CONF_API_KEY: "test-token"}
    mock_setup_entry.assert_not_called()

    mock_client.get_event.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "replacement-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: "replacement-token"}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)


@pytest.mark.parametrize("api_key", ["replacement-token", "test-token"])
async def test_reconfigure_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    api_key: str,
) -> None:
    """Keep the flow open after a duplicate key and allow a retry."""
    assert await async_setup_component(hass, DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "other-token"})
    other_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert next(iter(result["data_schema"].schema)).description == {
        "suggested_value": "test-token"
    }
    assert result["errors"] == {CONF_API_KEY: "already_configured"}
    assert mock_config_entry.data == {CONF_API_KEY: "test-token"}
    assert other_entry.data == {CONF_API_KEY: "other-token"}
    mock_client.get_event.assert_not_called()
    mock_setup_entry.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: api_key}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_API_KEY: api_key}
    assert other_entry.data == {CONF_API_KEY: "other-token"}
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry, other_entry]
    mock_client.get_event.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)
