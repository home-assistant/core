"""Verify Dobiss setup validation and duplicate handling."""

from asyncio import Event
from unittest.mock import AsyncMock

from dobiss_nxt import (
    DobissAuthenticationError,
    DobissConnectionError,
    DobissProtocolError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import USER_INPUT

pytestmark = pytest.mark.usefixtures("mock_client", "mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Validate both discovery and initial status before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].state is ConfigEntryState.LOADED
    mock_client.discover_lights.assert_awaited_once()
    mock_client.light_states.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (DobissAuthenticationError, "invalid_auth"),
        (DobissConnectionError, "cannot_connect"),
        (DobissProtocolError, "cannot_connect"),
    ],
)
async def test_errors_and_recovery(
    hass: HomeAssistant, mock_client: AsyncMock, exception: type[Exception], error: str
) -> None:
    """Keep the form usable after a failed connection."""
    mock_client.discover_lights.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_client.discover_lights.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Do not create a second configuration for the same normalized host."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT | {"host": "DOBISS.local"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.discover_lights.assert_awaited_once()


async def test_invalid_host(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Reject an unexpected URL without contacting it."""
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT | {"host": "http://dobiss.local/path"}
    )
    assert result["errors"] == {"host": "invalid_host"}
    mock_client.discover_lights.assert_not_called()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_status_error(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Discovery alone is insufficient to validate setup."""
    mock_client.light_states.side_effect = DobissConnectionError
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "cannot_connect"}
    mock_client.light_states.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_empty_secret(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Handle a missing secret without creating a client."""
    result = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT | {"api_secret": ""}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    mock_client.discover_lights.assert_not_called()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_concurrent_duplicate(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Recheck the host when another flow finishes during API validation."""
    first = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        "dobiss", context={"source": SOURCE_USER}
    )
    validation_started = Event()
    release_validation = Event()

    async def delayed_status(*args: object, **kwargs: object) -> dict[str, int]:
        validation_started.set()
        await release_validation.wait()
        return {"4_0": 50, "2_0": 0}

    mock_client.light_states.side_effect = delayed_status
    pending = hass.async_create_background_task(
        hass.config_entries.flow.async_configure(first["flow_id"], USER_INPUT),
        "Dobiss delayed setup validation",
    )
    await validation_started.wait()
    mock_client.light_states.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        second["flow_id"], USER_INPUT | {"host": "DOBISS.local"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    release_validation.set()
    result = await pending
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries("dobiss")) == 1
    await hass.async_block_till_done()
