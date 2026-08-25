"""Test the Haus-Bus config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def _resolve_progress(hass: HomeAssistant, flow_id: str) -> dict:
    """Poll a config flow until it completes."""
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    while result["type"] is FlowResultType.SHOW_PROGRESS:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(flow_id)
    return result


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Test the user flow finds a device and creates a config entry."""
    mock_home_server.is_any_device_found.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _resolve_progress(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Haus-Bus"
    assert result["data"] == {}

    # Creating the entry triggers its own setup, which starts a second,
    # independent discovery via HausbusGateway.start_discovery() - the
    # config flow's own search only confirms a device exists before the
    # cover platform (and its dispatcher listeners) are even set up, so a
    # fresh search is needed afterwards to actually populate entities.
    # Both go through the same per-hass HomeServer, so the mock sees both.
    await hass.async_block_till_done()
    assert mock_home_server.searchDevices.call_count == 2


@pytest.mark.timeout(15)
async def test_user_flow_search_timeout_then_retry(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Test the user flow offers a retry when no device is found in time."""
    mock_home_server.is_any_device_found.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _resolve_progress(hass, result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search_timeout"

    # Retrying completes when a device is found.
    mock_home_server.is_any_device_found.return_value = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _resolve_progress(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("exc", [OSError("socket error"), OSError()])
async def test_user_flow_oserror_shows_retry(
    hass: HomeAssistant, mock_home_server: MagicMock, exc: Exception
) -> None:
    """Test that an OSError during discovery lands on the search_timeout retry form."""
    mock_home_server.searchDevices.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _resolve_progress(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search_timeout"


async def test_single_instance_allowed(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Test that only a single Haus-Bus config entry is allowed."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
